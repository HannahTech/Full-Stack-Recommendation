import requests, time, random, spacy, sqlite3, csv
from bs4 import BeautifulSoup
from urllib.parse import quote
import os, re, json
from flask import Flask, request, jsonify, render_template, Response

app = Flask(__name__, static_url_path='/static')

user_agents_list = [
    'Mozilla/5.0 (iPad; CPU OS 12_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.83 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.51 Safari/537.36'
]

def extract_materials(text):
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)
    
    known_materials = ["leather", "steel", "rubber", "silicone", "nylon", "canvas", "metal", "ceramic", "wood", "fabric", "resin", "titanium", "silicone", "mesh", "elastic", "polyamide", "braided"]

    materials = [token.text for token in doc if token.text.lower() in known_materials]

    product_pieces = None

    piece_match = re.search(r'(\d+)\s*(pc|pcs|piece)', text, re.IGNORECASE)
    if piece_match:
        product_pieces = int(piece_match.group(1))
    else:
        product_pieces = None

    return {"materials": materials, "product_pieces": product_pieces}

def scrape_shein_pages(search):
    yield 0
    base_url = "https://ca.shein.com/pdsearch/"
    products_list = []

    for page in range(1, 2):

        encoded_search = quote(search)
        url = base_url + encoded_search + "/?ici=s1&page=" + str(page)

        response = requests.get(url, headers={'User-Agent': random.choice(user_agents_list)})
        content = response.content
        soup = BeautifulSoup(content, 'html.parser')

        product_cards = soup.find_all('div', class_='product-card__bottom-wrapper') 
        
        total_cards = len(product_cards)
        processed_cards = 0

        for card in product_cards:
            product_dict = {}
            # Product Name
            product_name_elem = card.find('a', class_='goods-title-link')
            product_dict['Product Name'] = product_name_elem.text if product_name_elem else 'N/A'
            # Rank Category
            rank_sub_elem = card.find('span', class_='rank-sub')
            product_dict['Rank Category'] = rank_sub_elem.text if rank_sub_elem else 'N/A'
            # Rank Title
            rank_title_elem = card.find('span', class_='rank-title')
            product_dict['Rank Title'] = rank_title_elem.text if rank_title_elem else 'N/A'
            # Review Number
            star_text_elem = card.find('p', class_='start-text')
            product_dict['Review Number'] = star_text_elem.text if star_text_elem else 'N/A'
            # Sold Number
            star_num_elem = card.find('p', class_='product-card__selling-proposition-text font-golden')
            product_dict['Sold Number'] = star_num_elem.text if star_num_elem else 'N/A'
            # Price
            price_elem = card.find('div', class_='bottom-wrapper__price-wrapper').find('p', class_='product-item__camecase-wrap').find('span')
            product_dict['Price'] = float(price_elem.text[3:]) if price_elem else 'N/A'

            extract = extract_materials(product_dict['Product Name'].lower())
            product_dict['Material'] = extract['materials']
            product_dict['Pieces'] = extract['product_pieces']

            products_list.append(product_dict)

            processed_cards += 1
            progress = int((processed_cards / total_cards) * 100)
            yield progress, product_dict
    yield 100, product_dict

def save_to_csv(data, filename):
    with open(filename, mode='w', newline='', encoding='utf-8') as file:
        fieldnames = data[0].keys()
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        
        writer.writeheader()
        for row in data:
            writer.writerow(row)

def save_to_database(data):
    if os.path.exists('shein_data.db'):
        os.remove('shein_data.db')  
        
    conn = sqlite3.connect('shein_data.db')
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            product_name TEXT,
            rank_category TEXT,
            rank_title TEXT,
            review_number TEXT,
            sold_number TEXT,
            price REAL,
            material TEXT,
            pieces INT
        )
    ''')

    for product in data:
        material_str = ', '.join(product['Material']) if isinstance(product['Material'], list) else product['Material']

        cursor.execute('''
            INSERT INTO products (product_name, rank_category, rank_title, review_number, sold_number, price, material, pieces)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            product['Product Name'],
            product['Rank Category'],
            product['Rank Title'],
            product['Review Number'],
            product['Sold Number'],
            product['Price'],
            material_str,
            product['Pieces']
        ))

    conn.commit()
    conn.close()

def get_non_empty_pages(search):
    while True:
        some_pages = scrape_shein_pages(search)
        if some_pages:
            return some_pages


# def get_non_empty_pages(search):
#     while True:
#         some_pages = scrape_shein_pages(search)
#         if len(some_pages) > 0:
#             return some_pages

# some_pages = get_non_empty_pages("apple watch band", 1)

def generate_progress():
    progress = 0
    while progress < 100:
        time.sleep(0.1) 
        progress += 5  
        yield str(progress)
    yield 'done'


def material(search):
    progress_generator = scrape_shein_pages(search)

    for progress, product_dict in progress_generator:
        yield f"data:{progress}\n"
        yield f"data:{progress}\ndata:{json.dumps(product_dict)}\n\n"

    some_pages = get_non_empty_pages(search)

    save_to_csv(some_pages, 'shein_data.csv')
    save_to_database(some_pages)

    one_piece_products = [product for product in some_pages if product['Pieces'] == 1]
    material_prices = {}
    for product in one_piece_products:
        for material in product['Material']:
            if material not in material_prices:
                material_prices[material] = []
            material_prices[material].append(product['Price'])
    price_per_piece = {material: round(sum(prices) / len(prices), 2) for material, prices in material_prices.items()}
    sorted_materials = sorted(price_per_piece.items(), key=lambda x: x[1], reverse=True)
    cheapest_products = sorted(one_piece_products, key=lambda x: x['Price'])
    if sorted_materials:
        good_material = sorted_materials[0][0]
        cheapest_good_material = [product for product in cheapest_products if good_material in product['Material']][:5]
        for product in cheapest_good_material:
            yield f"Material: {good_material}, Price: {product['Price']}, Product Name: {product['Product Name']}\n\n"
    else:
        print("No materials found.")
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['GET', 'POST'])
def search():
    search_input = request.form.get('searchInput', 'apple watch band')
    if not search_input:
        search_input = 'apple watch band'
    
    progress_generator = material(search_input)
    
    def generate():
        for progress in progress_generator:
            yield f"data:{progress}\n\n"
    
    return Response(generate(), content_type='text/event-stream')


if __name__ == '__main__':
    app.run(debug=True)