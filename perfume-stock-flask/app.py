import os
from flask import Flask, render_template, request, redirect
from datetime import datetime
from pymongo import MongoClient

app = Flask(__name__)

# Koneksi MongoDB
client = MongoClient(os.environ.get('MONGO_URI'))
db = client[os.environ.get('DB_NAME', 'perfume_stock')]

# Collections
perfumes_collection = db.perfumes
sales_collection = db.sales
paylater_sales_collection = db.paylater_sales
finances_collection = db.finances

# Inisialisasi data awal jika collection kosong
if perfumes_collection.count_documents({}) == 0:
    initial_perfumes = [
        {'id': 1, 'name': 'Vanilla Verve', 'stock': 100, 'price': 200000, 'is_active': True},
        {'id': 2, 'name': 'Angel Man', 'stock': 100, 'price': 200000, 'is_active': True},
        {'id': 3, 'name': 'Midnight Of Summer', 'stock': 100, 'price': 200000, 'is_active': True},
        {'id': 4, 'name': 'Midnight Blues', 'stock': 100, 'price': 200000, 'is_active': True},
        {'id': 5, 'name': 'Davidov Cool Water', 'stock': 100, 'price': 200000, 'is_active': True},
        {'id': 6, 'name': 'Peach Perfection', 'stock': 100, 'price': 200000, 'is_active': True},
        {'id': 7, 'name': 'Mystical Mirage', 'stock': 50, 'price': 150000, 'is_active': False}
    ]
    perfumes_collection.insert_many(initial_perfumes)

@app.route('/')
def index():
    perfumes = list(perfumes_collection.find())
    return render_template('index.html', perfumes=perfumes)

@app.route('/add', methods=['GET', 'POST'])
def add():
    if request.method == 'POST':
        last_perfume = perfumes_collection.find_one(sort=[('id', -1)])
        new_id = 1 if last_perfume is None else last_perfume['id'] + 1
        
        new_perfume = {
            'id': new_id,
            'name': request.form['name'],
            'stock': int(request.form['stock']),
            'price': float(request.form['price']),
            'is_active': True
        }
        perfumes_collection.insert_one(new_perfume)
        return redirect('/')
    return render_template('add.html')

@app.route('/toggle/<int:id>')
def toggle(id):
    perfume = perfumes_collection.find_one({'id': id})
    if perfume:
        perfumes_collection.update_one(
            {'id': id},
            {'$set': {'is_active': not perfume['is_active']}}
        )
    return redirect('/')

@app.route('/sales')
def sales_page():
    sales = list(sales_collection.find())
    total_sales = sum(sale['total_amount'] for sale in sales)
    return render_template('sales.html', sales=sales, total_sales=total_sales)

@app.route('/add_sale', methods=['GET', 'POST'])
def add_sale():
    if request.method == 'POST':
        perfume_id = int(request.form['perfume_id'])
        quantity = int(request.form['quantity'])
        customer_name = request.form['customer_name']
        notes = request.form['notes']
        payment_method = request.form['payment_method']
        
        selected_perfume = next((p for p in perfumes if p['id'] == perfume_id), None)
        
        if selected_perfume:
            total_amount = selected_perfume['price'] * quantity
            
            sale_data = {
                'id': len(sales) + len(paylater_sales) + 1,
                'perfume_name': selected_perfume['name'],
                'quantity': quantity,
                'price_per_item': selected_perfume['price'],
                'total_amount': total_amount,
                'customer_name': customer_name,
                'notes': notes,
                'payment_method': payment_method,
                'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'status': 'pending' if payment_method == 'paylater' else 'paid'
            }
            
            if payment_method == 'paylater':
                paylater_sales_collection.insert_one(sale_data)
            else:
                sales_collection.insert_one(sale_data)
                finance_data = {
                    'id': len(finances) + 1,
                    'description': f"Penjualan {selected_perfume['name']} ({quantity} pcs) - {customer_name}",
                    'type': 'income',
                    'amount': total_amount,
                    'payment_method': payment_method,
                    'notes': notes,
                    'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                finances_collection.insert_one(finance_data)
            
            selected_perfume['stock'] -= quantity
            perfumes_collection.update_one(
                {'id': selected_perfume['id']},
                {'$set': {'stock': selected_perfume['stock']}}
            )
            
            return redirect('/sales')
    
    active_perfumes = list(perfumes_collection.find({'is_active': True}))
    return render_template('add_sale.html', perfumes=active_perfumes)

@app.route('/edit_sale/<int:id>', methods=['GET', 'POST'])
def edit_sale(id):
    sale = sales_collection.find_one({'id': id})
    if not sale:
        return redirect('/sales')
    
    if request.method == 'POST':
        perfume_id = int(request.form['perfume_id'])
        quantity = int(request.form['quantity'])
        customer_name = request.form['customer_name']
        notes = request.form['notes']
        payment_method = request.form['payment_method']
        
        perfume = perfumes_collection.find_one({'id': perfume_id})
        if perfume:
            total_amount = perfume['price'] * quantity
            
            sales_collection.update_one(
                {'id': id},
                {'$set': {
                    'perfume_name': perfume['name'],
                    'quantity': quantity,
                    'price_per_item': perfume['price'],
                    'total_amount': total_amount,
                    'customer_name': customer_name,
                    'notes': notes,
                    'payment_method': payment_method
                }}
            )
            
            finances_collection.update_one(
                {'description': {'$regex': f"Penjualan.*{sale['perfume_name']}.*{sale['customer_name']}"}},
                {'$set': {
                    'description': f"Penjualan {perfume['name']} ({quantity} pcs) - {customer_name}",
                    'amount': total_amount,
                    'payment_method': payment_method,
                    'notes': notes
                }}
            )
            
            return redirect('/sales')
    
    active_perfumes = list(perfumes_collection.find({'is_active': True}))
    return render_template('edit_sale.html', sale=sale, perfumes=active_perfumes)

@app.route('/delete_sale/<int:id>')
def delete_sale(id):
    sale = sales_collection.find_one({'id': id})
    if sale:
        sales_collection.delete_one({'id': id})
        
        # Hapus data keuangan terkait
        finances_collection.delete_one({
            'description': {'$regex': f"Penjualan.*{sale['perfume_name']}.*{sale['customer_name']}"}
        })
    
    return redirect('/sales')

@app.route('/paylater')
def paylater():
    paylater_sales = list(paylater_sales_collection.find())
    return render_template('paylater.html', paylater_sales=paylater_sales)

@app.route('/update_paylater/<int:id>', methods=['POST'])
def update_paylater(id):
    payment_method = request.form['payment_method']
    
    sale = paylater_sales_collection.find_one({'id': id})
    if sale:
        sale['payment_method'] = payment_method
        sale['status'] = 'paid'
        sales_collection.insert_one(sale)
        paylater_sales_collection.delete_one({'id': id})
        
        finance_data = {
            'id': len(list(finances_collection.find())) + 1,
            'description': f"Pembayaran Paylater - {sale['perfume_name']} - {sale['customer_name']}",
            'type': 'income',
            'amount': sale['total_amount'],
            'payment_method': payment_method,
            'notes': sale['notes'],
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        finances_collection.insert_one(finance_data)
    
    return redirect('/paylater')

@app.route('/finance')
def finance():
    finances = list(finances_collection.find())
    total_income = sum(f['amount'] for f in finances if f['type'] == 'income')
    expenses = sum(f['amount'] for f in finances if f['type'] == 'expense')
    
    return render_template('finance.html', 
                         finances=finances,
                         total_income=total_income,
                         expenses=expenses)

@app.route('/toggle_finance/<int:id>')
def toggle_finance(id):
    finance = finances_collection.find_one({'id': id})
    if finance:
        finances_collection.update_one(
            {'id': id},
            {'$set': {'is_active': not finance.get('is_active', True)}}
        )
    return redirect('/finance')

@app.route('/edit_finance/<int:id>', methods=['POST'])
def edit_finance(id):
    finances_collection.update_one(
        {'id': id},
        {'$set': {
            'description': request.form['description'],
            'notes': request.form['notes']
        }}
    )
    return redirect('/finance')

@app.route('/dashboard')
def dashboard():
    total_products = perfumes_collection.count_documents({})
    active_products = perfumes_collection.count_documents({'is_active': True})
    total_stock = sum(p['stock'] for p in perfumes_collection.find())
    
    sales = list(sales_collection.find())
    total_sales = sum(sale['total_amount'] for sale in sales)
    
    return render_template('dashboard.html',
                         total_products=total_products,
                         active_products=active_products,
                         total_stock=total_stock,
                         total_sales=total_sales)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)