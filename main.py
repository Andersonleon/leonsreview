
from ollama import generate
import requests
from requests.auth import HTTPBasicAuth
from Product import *
import requests
from io import BytesIO
from PIL import Image, ImageOps
from datetime import datetime
import random
import dotenv

dotenv.load_dotenv()


def getReviewData():
    with open("review.txt", "r", encoding="utf-8") as f:
        reviewData = f.read()
    return reviewData



def createReview(reviewData, media_id):

    response = generate('leon', f'{reviewData}')
    bot_response = response['response']

    specs_table = generate_specs_table(ProductSpecs)
    bot_response += f"<br><h2>{ProductTitle} Specifications</h2>{specs_table}"

    bot_response = bot_response + f""" 
    <br> If you would like to know more about the {ProductTitle}, you can check out the amazon page for it <a href="{ProductLink}">here</a>.
    """

    response = generate('leonexcerp', f'{bot_response}')
    exerp = response['response']

    response = generate('leonmeta', f'{bot_response}')
    meta = response['response']
    
    createwebpage(bot_response, media_id, exerp, meta)


def generate_specs_table(specs):

    table_html = """
    <table border="1" style="width:60%; border-collapse: collapse; text-align: left;">
        <tr><th>Specification</th><th>Details</th></tr>
    """
    for key, value in specs.items():
        table_html += f"<tr><td>{key}</td><td>{value}</td></tr>"
    table_html += "</table>"
    return table_html

def createmedia():
    WP_URL = "https://leonsreview.com/wp-json/wp/v2/media"
    USERNAME = dotenv.get("USERNAME")
    PASSWORD = dotenv.get("PASSWORD")
    
    try:
        # Download the image from the link
        image_response = requests.get(ProductImage, stream=True)
        image_response.raise_for_status()
        
        # Open image and convert to webp format
        image = Image.open(BytesIO(image_response.content))
        
        # Resize while maintaining aspect ratio, add padding if Image is smaller than target size
        target_size = (1080, 720)

        colour1 = random.randint(0, 255)
        colour2 = random.randint(0, 255)
        colour3 = random.randint(0, 255)

        image = ImageOps.pad(image, target_size, color=(colour1, colour2, colour3))  # Create a random background colour
        
        webp_buffer = BytesIO()
        image.save(webp_buffer, format="WEBP", quality=80) # convert to  webp format
        webp_buffer.seek(0)
        
        filename = ProductTitle + ".webp"
        
        # add metadata to the image
        files = {
            'file': (filename, webp_buffer, 'image/webp'),
            'caption': (None, f"An image of the {ProductTitle}"),
            'alt_text': (None, f"An image of the {ProductTitle}"),
            'description': (None, f"An image of the {ProductTitle}"),
        }
        
        # Upload the file to the WP media library
        response = requests.post(WP_URL, files=files, auth=HTTPBasicAuth(USERNAME, PASSWORD))
        response.raise_for_status() #If issue 
        
        # Get media ID 
        media_id = response.json().get("id")
        return media_id
    
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
    except KeyError as e:
        print(f"Error: Missing key in response headers: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    
    return None

def get_category_id(WP_URL, USERNAME, PASSWORD):

    # Get catagory ID

    try:
        response = requests.get(f"{WP_URL}/categories", auth=HTTPBasicAuth(USERNAME, PASSWORD))
        response.raise_for_status()
        categories = response.json()
        
        for category in categories:
            if category['name'].lower() == Catagory.lower():  # Ensure exact match, case insensitive
                return category['id']
        
        return None  # Category not found
    except requests.exceptions.RequestException as e:
        print(f"Error retrieving category: {e}")
        return None
    
def get_or_create_tags(WP_URL, USERNAME, PASSWORD, tags):
    # Get or create tags if they do not exist
    tag_ids = []
    headers = {'Content-Type': 'application/json'}
    
    for tag in tags:
        try:
            response = requests.get(f"{WP_URL}/tags?search={tag}", auth=HTTPBasicAuth(USERNAME, PASSWORD))
            response.raise_for_status()
            tag_data = response.json()

            if tag_data:
                tag_ids.append(tag_data[0]['id'])
            else:
                tag_payload = {"name": tag}
                response = requests.post(f"{WP_URL}/tags", json=tag_payload, headers=headers, auth=HTTPBasicAuth(USERNAME, PASSWORD))
                response.raise_for_status()
                tag_ids.append(response.json().get("id"))

        except requests.exceptions.RequestException as e:
            print(f"Error retrieving/creating tag '{tag}': {e}")

    return tag_ids


def createwebpage(bot_response, media_id, exerp, meta):

    WP_URL = "https://leonsreview.com/wp-json/wp/v2/posts"
    USERNAME = dotenv.get("USERNAME")
    PASSWORD = dotenv.get("PASSWORD")

    category_id = get_category_id("https://leonsreview.com/wp-json/wp/v2", USERNAME, PASSWORD)

    if category_id is None:
        print(f"Category {Catagory} not found. Cannot create post.")
        return

    tags = [ProductTitle, Catagory] + Tags.split(", ")  # Include predefined tags from Product.py
    tag_ids = get_or_create_tags("https://leonsreview.com/wp-json/wp/v2", USERNAME, PASSWORD, tags)

    # Schema Markup
    schema_markup = f"""
    <script type="application/ld+json">
    {{
        "@context": "https://schema.org/",
        "@type": "Review",
        "itemReviewed": {{
            "@type": "Product",
            "name": "{ProductTitle}",
            "image": "{ProductImage}",
            "url": "{ProductLink}"
        }},
        "reviewRating": {{
            "@type": "Rating",
            "ratingValue": "{ProductRating}",
            "bestRating": "5"
        }},
        "author": {{
            "@type": "Person",
            "name": "Leon"
        }},
        "datePublished": "{datetime.today().strftime('%Y-%m-%d')}",
        "reviewBody": "{bot_response}"
    }}
    </script>
    """

    # OpenGraph Metadata
    og_metadata = f"""
    <meta property="og:type" content="article">
    <meta property="og:title" content="{ReviewTitle}">
    <meta property="og:description" content="{exerp}">
    <meta property="og:image" content="{ProductImage}">
    <meta property="og:url" content="{ProductLink}">
    <meta property="og:site_name" content="LeonsReview">
    """

    # Combine Schema Markup and OpenGraph Metadata with bot response
    full_content = schema_markup + og_metadata + bot_response

    # Page content with tags, categories, and media
    page_data = {
        "title": ReviewTitle,
        "content": full_content,
        "categories": category_id,
        "tags": tag_ids,
        "featured_media": media_id,
        "excerpt": exerp,
        "description": meta,
        "status": "publish",
    }

    #create the page
    response = requests.post(WP_URL, json=page_data, auth=HTTPBasicAuth(USERNAME, PASSWORD))

    # Print response
    if response.status_code == 201:
        print("Page created successfully:", response.json().get("link"))
    else:
        print("Error:", response.text)

    print(meta) 



if __name__ == "__main__":
    media_id = createmedia()
    if media_id:
        reviewData = getReviewData()
        createReview(reviewData, media_id)
    