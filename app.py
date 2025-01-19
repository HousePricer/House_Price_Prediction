from flask import Flask, render_template, request, session, redirect, url_for, jsonify ,flash,send_from_directory, abort
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer
from flask_session import Session
from pymongo import MongoClient
import random
import string
import requests
import os
from bson import json_util
from bson import ObjectId
import pandas as pd
import xgboost as xgb
import joblib
# Create the Flask application
app = Flask(__name__)
app.secret_key = 'your-strong-secret-key'

# Configure mail settings
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USERNAME'] = 'jyothsnameduri9999@gmail.com'
app.config['MAIL_PASSWORD'] = 'qztfjotakitawugw'
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False

mail = Mail(app)
s = URLSafeTimedSerializer(app.secret_key)

# MongoDB configuration
mongodb_uri = 'mongodb://localhost:27017/'
client = MongoClient(mongodb_uri)
db = client['Mydatabase']  
collection = db['users']
admincollection = db['admin']
propertiescollection = db['properties']
adminrequests = db['Admin_Requests']
searchdata = db['search_data']
# Add a new collection for prediction history
historycollection = db['prediction_history']

# Configure Flask-Session
app.config['SESSION_TYPE'] = 'mongodb'
app.config['SESSION_MONGODB'] = client
app.config['SESSION_MONGODB_DB'] = 'flask_sessions'
app.config['SESSION_MONGODB_COLLECT'] = 'sessions'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True


# Add this line to specify the upload folder
app.config['UPLOAD_FOLDER'] = 'uploads'  # Make sure this folder exists

model = joblib.load('xgboost_real_estate_model.joblib')
label_encoders = joblib.load('label_encoders.joblib')

# Initialize the session extension
Session(app)

# OTP generation and storage
otps = {}
unique_titles_and_locations = []
def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def fetch_geonames(geoname_id, username):
    url = f"http://api.geonames.org/childrenJSON?geonameId={geoname_id}&username={username}"
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        geonames = data.get('geonames', [])
        names = [entry['name'] for entry in geonames]
        return names
    else:
        print(f"Failed to fetch data. Status code: {response.status_code}")
        return []

@app.route('/send_otp', methods=['POST'])
def send_otp():
    email = request.json.get('email')
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400

    otp = generate_otp()
    otps[email] = otp

    msg = Message('Your OTP', sender='jyothsnameduri9999@gmail.com', recipients=[email])
    msg.body = f'Your OTP is {otp}'
    try:
        mail.send(msg)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    
@app.route('/verify_otp', methods=['POST'])
def verify_otp():
    email = request.json.get('email')
    otp = request.json.get('otp')

    if not email or not otp:
        return jsonify({'success': False, 'message': 'Email and OTP are required'}), 400

    if otps.get(email) == otp:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'message': 'Invalid OTP'}), 400

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/admin')
def admin():
    admin_ID = session.get('admin_ID')
    if(admin_ID):
        arequests = adminrequests.find()
        return render_template('admin.html', id=admin_ID,properties = arequests)
    else:
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>
<body>
    <button id="login-btn">Login</button>
    
</body>
<script>
    document.getElementById('login-btn').onclick = ()=>{
        window.location.href = "/adminlogin"
    }
    document.getElementById('signup-btn').onclick = ()=>{
        window.location.href = "/adminsignup"
    }
</script>
</html>"""

@app.route('/adminlogin')
def adminlogin():
    return render_template('adminlogin.html')

@app.route('/adminsignup')
def adminsignup():
    return render_template('adminsignup.html')

@app.route('/predict_price')
def predict_price():
    return render_template('predict.html')

@app.route('/postproperty')
def postpropert():
    email = session.get('email')
    if email:
        # Render the template for logged-in users
        print(session.get('fullname'))
        return render_template('postproperty.html',fullname=session.get('fullname'),email = session.get('email'))
    else:
        # Render the template for non-logged-in users
        return render_template('fornonloggedin.html')
    

@app.route('/')
def get_email():
    email = session.get('email')
    properties_cursor = propertiescollection.find()
    properties = [json_util.loads(json_util.dumps(property)) for property in properties_cursor]
    location_titles = set()
    for property in properties:
        # Extract Title
        title = property.get('Title')
        if title and title not in unique_titles_and_locations:
            unique_titles_and_locations.append(title)  # Add title to the list

        # Extract location details
        country = property.get('country')
        state = property.get('state')
        city = property.get('city')
        sub_city = property.get('sub_city')
        area1 = property.get('area1')
        area2 = property.get('area2')
        area3 = property.get('area3')

        # Add locations to the set to ensure uniqueness
        for location in [country, state, city, sub_city, area1, area2, area3]:
            if location and location not in location_titles:
                if location not in unique_titles_and_locations:
                    unique_titles_and_locations.append(location)
        print(unique_titles_and_locations)


    if email:
        return render_template('forloggedin.html', email=email, fullname=session.get('fullname'), properties=properties)
    else:
        return render_template('fornonloggedin.html', properties=properties)


@app.route('/registering', methods=['POST', 'GET'])
def register():
    fullname = request.form.get('fullname')
    email = request.form.get('email')
    password = request.form.get('password')  

    if not fullname or not email or not password:
        return "<h1>All fields are required</h1>"

    if collection.find_one({'email': email}):
        return "<h1>Email already present</h1>"

    result = collection.insert_one({
        'fullname': fullname,
        'email': email,
        'password': password,
        'Your_Properties':[]
    })


    
    if result.inserted_id:
        return redirect(url_for('login'))
    else:
        return "<h1>Failed to register user</h1>"
    
@app.route('/autocomplete', methods=['GET'])
def autocomplete():
    query = request.args.get('q', '').lower()
    # Filter names that start with the query string
    suggestions = [name for name in unique_titles_and_locations if name.lower().startswith(query)]
    return jsonify(suggestions[:10])

@app.route('/logging', methods=['POST', 'GET'])
def logging():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user = collection.find_one({'email': email, 'password': password})
        if user:
            session['email'] = email
            session['fullname'] = user.get('fullname', 'User')
            return redirect(url_for('get_email'))
        flash('Invalid username or password. Please try again.')
        return redirect(url_for('login'))

    return render_template('login.html')
@app.route('/adminlogging', methods=['GET', 'POST'])
def adminlogginig():
    id = request.form.get('id')
    id = str(id)
    password = request.form.get('password')
    password = str(password)
    admin = admincollection.find_one({'id': id, 'password': password})
    
    if admin:
        session['admin_ID'] = id
        return redirect(url_for('admin'))
    else:
        # Handle invalid credentials
        return "Invalid ID or password", 401  
@app.route('/adminsigning',methods=['GET','POST'])
def adminsigning():
    id = request.form.get('id')
    password = request.form.get('password')
    result = admincollection.insert_one({
        'id':id,
        'password':password
    })
    if(result):
        return redirect(url_for('adminlogin'))
    

  # Replace 'YOUR_CLIENT_ID' with your actual Imgur client ID
@app.route('/post', methods=['GET', 'POST'])
def postingproperty():
    if session.get('email'):
        image_urls = []  # Initialize an empty list to store image URLs

        # Loop through each uploaded file
        for i in range(1, 4):  # Assuming you have three input fields for images
            uploaded_file = request.files.get(f'photo{i}')  # Get each photo input

            if uploaded_file and uploaded_file.filename != '':
                try:
                    # Save the file locally
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
                    uploaded_file.save(file_path)  # Save the uploaded file
                    # Generate the URL to access the uploaded image
                    image_url = f"http://localhost:5000/{app.config['UPLOAD_FOLDER']}/{uploaded_file.filename}"
                    image_urls.append(image_url)  # Append the image URL to the list
                except Exception as e:
                    app.logger.error(f'Error uploading image: {e}')
                    return jsonify({"error": "Image upload failed"}), 500
            else:
                app.logger.info(f'No image uploaded for photo{i}.')

        form_data = {
            'Ownername': session.get('fullname'),
            'Owneremail': session.get('email'),
            'Title': request.form.get('title'),
            'purpose': request.form.get('purpose'),
            'country': request.form.get('country'),
            'state': request.form.get('state'),
            'city': request.form.get('city'),
            'sub_city': request.form.get('sub_city'),
            'area1': request.form.get('area1'),
            'area2': request.form.get('area2'),
            'area3': request.form.get('area3'),
            'dono': request.form.get('dono'),
            'bedrooms': request.form.get('bedrooms'),
            'bathrooms': request.form.get('bathrooms'),
            'balcony': request.form.get('balcony'),
            'area': request.form.get('area'),
            'pricefrom': request.form.get('pricefrom'),
            'priceto': request.form.get('priceto'),
            'school': request.form.get('school'),
            'hospital': request.form.get('hospital'),
            'transport': request.form.get('transport'),
            'groceries_store': request.form.get('groceries_store'),
            'policestation': request.form.get('policestation'),
            'description': request.form.get('description'),
            'image_urls': image_urls,  # Store the list of image URLs
            'verified': False
        }    
        # Debugging: Print form data to console
        app.logger.debug(f'Form data received: {form_data}')

        try:
            # Insert the form data into MongoDB
            result = adminrequests.insert_one(form_data)
            user_email = session.get('email')  # Assign value to user_email here
            
            update_result = collection.update_one(
                {'email': user_email},
                {'$push': {'Your_Properties': form_data}}
            )
            app.logger.info('Data inserted into MongoDB successfully.')
            
            return redirect(url_for('get_email'))
        except Exception as e:
            app.logger.error(f'Error inserting data into MongoDB: {e}')
            return jsonify({"error": "Data insertion failed"}), 500
    else:
        # Render the template for non-logged-in users
        return redirect(url_for('login'))
@app.route('/property/<property_id>', methods=['GET'])
def view_property(property_id):

    property_data = propertiescollection.find_one({'_id': ObjectId(property_id)})
    
    if property_data:
        # Render a template with the property details
        return render_template('property_details.html', property=property_data,email = session.get('email'))
    else:
        return "Property not found", 404
@app.route('/admin_requests/<property_id>', methods=['GET'])
def admin_view_property(property_id):
    admin_ID = session.get('admin_ID')
    if(admin_ID):
        property_data = adminrequests.find_one({'_id': ObjectId(property_id)})
        
        if property_data:
            # Render a template with the property details
            return render_template('admin_property_details.html', property=property_data)
        else:
            return "Property not found", 404
    else:
        return redirect(url_for('admin'))
@app.route('/search', methods=['GET'])
def search_houses():
    area_name = request.args.get('areaName')
    property_type = request.args.get('propertyType')  # Get property type from query parameters

    # Initialize the MongoDB query
    query = {
        "$or": [
            {"Title": {"$regex": area_name, "$options": "i"}},
            {"state": {"$regex": area_name, "$options": "i"}},
            {"city": {"$regex": area_name, "$options": "i"}},
            {"area1": {"$regex": area_name, "$options": "i"}},
            {"area2": {"$regex": area_name, "$options": "i"}},
            {"area3": {"$regex": area_name, "$options": "i"}},
            {"country": {"$regex": area_name, "$options": "i"}}
        ]
    }
    # If a property type is provided, add it to the query
    if property_type:
        query['purpose'] = property_type
    if area_name:
        houses = propertiescollection.find(query)
        house_list = []
        for house in houses:
            house_list.append({
                "image_url": house.get("image_urls", [None])[0],
                "owner_name": house.get("Ownername", 'N/A'),
                "owner_email": house.get("Owneremail", 'N/A'),
                "purpose": house.get("purpose", 'N/A'),
                "country": house.get("country", 'N/A'),
                "state": house.get("state", 'N/A'),
                "city": house.get("city", 'N/A'),
                "bedrooms": house.get("bedrooms", 'N/A'),
                "bathrooms": house.get("bathrooms", 'N/A'),
                "balcony": house.get("balcony", 'N/A'),
                "area": house.get("area", 'N/A'),
                "price_from": house.get("pricefrom", 'N/A'),
                "price_to": house.get("priceto", 'N/A'),
                "school": house.get("school", 'N/A'),
                "hospital": house.get("hospital", 'N/A'),
                "transport": house.get("transport", 'N/A'),
                "groceries_store": house.get("groceries_store", 'N/A'),
                "policestation": house.get("policestation", 'N/A'),
                "description": house.get("description", 'N/A'),
                "product_id": str(house.get("_id", 'N/A'))  # Convert ObjectId to string
            })
        return jsonify(house_list)
    
    return jsonify({"error": "Area name not provided"}), 400
@app.route('/admin_requests/<string:product_id>/accept', methods=['GET'])
def accept_request(product_id):
    admin_ID = session.get('admin_ID')
    if(admin_ID):
        try:
            # Step 1: Find the property request from adminrequests
            property_data = adminrequests.find_one({'_id': ObjectId(product_id)})
            
            if not property_data:
                return "<h1>Property request not found</h1>", 404
            
            # Step 2: Extract user email
            user_email = property_data.get('Owneremail')
            property_title = property_data.get('Title')
            
            if not user_email:
                return "<h1>User email not found in property request</h1>", 404
            
            # Step 3: Find the user in the collection
            user_data = collection.find_one({'email': user_email})
            
            if not user_data:
                return "<h1>User not found</h1>", 404
            
            result = collection.update_one(
                {
                    "email": user_email,
                    "Your_Properties.Title": property_title
                },
                {
                    "$set": { "Your_Properties.$.verified": True }
                }
            )
            
            if result.matched_count == 0:
                return "<h1>Property not found in user's properties</h1>", 404
            
            propertiescollection.insert_one(property_data)
            
            # Step 5: Optionally delete the property request
            adminrequests.delete_one({'_id': ObjectId(product_id)})

            # Redirect to a relevant page after successful acceptance
            return redirect(url_for('admin'))  # Replace with your view

        except Exception as e:
            app.logger.error(f'Error processing request: {e}')
            return "<h1>Error occurred</h1>", 500
    else:
        return redirect(url_for('admin'))

@app.route('/reject_requests/<string:product_id>/reject', methods=['GET'])
def reject_request(product_id):
    admin_ID = session.get('admin_ID')
    if(admin_ID):
        # Step 1: Find the property request in the adminrequests collection
        property_data = adminrequests.find_one({'_id': ObjectId(product_id)})
        if not property_data:
            return "<h1>Property request not found</h1>", 404

        # Step 2: Extract user email and property title
        user_email = property_data.get('Owneremail')
        property_title = property_data.get('Title')

        if not user_email:
            return "<h1>User email not found in property request</h1>", 404

        # Step 3: Find user in the collection by email
        user_data = collection.find_one({'email': user_email})
        if not user_data:
            return "<h1>User not found</h1>", 404

        # Step 4: Remove the property from the user's Your_Properties array
        result = collection.update_one(
            {
                "email": user_email  # Find the user by their email
            },
            {
                "$pull": { "Your_Properties": { "_id": ObjectId(product_id) } }  # Remove the property based on product_id
            }
        )
        adminrequests.delete_one({'_id': ObjectId(product_id)})
        # Check if the update was successful
        if result.modified_count == 0:
            return jsonify({'success': False, 'message': 'Failed to remove property or property not found'}), 500

        # Step 5: Send rejection email
        msg = Message(
            'Your Property is Rejected', 
            sender='jyothsnameduri9999@gmail.com', 
            recipients=[user_email]
        )
        msg.body = f'Your Property "{property_title}" is rejected due to technical issues or a lack of response.<br>For any queries, please contact findmynest@findmynest.com.'

        try:
            mail.send(msg)
            return redirect(url_for('admin'))
        except Exception as e:
            return jsonify({'success': False, 'message': str(e)}), 500
    else:
        return redirect(url_for('admin'))

@app.route('/profile',methods = ['GET'])
def profile():
    if session.get('email'):

        user_data = collection.find_one({'email': session.get('email')})
        return render_template('profile.html',user = user_data)  
@app.route('/delete_property/<property_id>', methods=['POST'])
def delete_property(property_id):
    user_email = session.get('email')
    user_data = collection.find_one({'email': user_email})
    try:
        result = propertiescollection.delete_one({"_id": ObjectId(property_id)})  # Delete the property by ID
        result = collection.update_one(
    {
        "email": user_email  # Find the user by their email
    },
    {
        "$pull": { "Your_Properties": { "_id": ObjectId(property_id) } }  # Remove the property based on product_id
    }
)
        return redirect(url_for('profile'))
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
from datetime import datetime
@app.route('/predict', methods=['GET', 'POST'])
def predict():
    if request.method == 'POST':
        # Extract input values from the form
        total_area = float(request.form['total_area'])
        price_per_sqft = float(request.form['price_per_sqft'])
        total_rooms = int(request.form['total_rooms'])
        balcony = request.form['balcony']
        city = request.form['city']
        property_type = request.form['property_type']
        bhk = int(request.form['bhk'])

        # Prepare the input data for prediction
        input_data = pd.DataFrame({
            'Total_Area(SQFT)': [total_area],
            'Price_per_SQFT': [price_per_sqft],
            'Total_Rooms': [total_rooms],
            'Balcony': [balcony],
            'city': [city],
            'property_type': [property_type],
            'BHK': [bhk]
        })

        for column in input_data.select_dtypes(include=['object']).columns:
            input_data[column] = label_encoders[column].transform(input_data[column])

        # Convert to DMatrix format
        dinput = xgb.DMatrix(input_data)

        # Make prediction
        prediction = model.predict(dinput)[0]
        predicted_price = int(prediction)

        # Store prediction in MongoDB
        prediction_data = {
            'total_area': total_area,
            'price_per_sqft': price_per_sqft,
            'total_rooms': total_rooms,
            'balcony': balcony,
            'city': city,
            'property_type': property_type,
            'bhk': bhk,
            'predicted_price': predicted_price,
            'timestamp': datetime.now()  # Add timestamp of prediction
        }

        # Insert prediction data into 'prediction_history' collection
        db.prediction_history.insert_one(prediction_data)

        # Query MongoDB for houses matching the predicted price range
        query = { "$and": [ 
            {"pricefrom": {"$lte": str(predicted_price)}}, 
            {"priceto": {"$gte": str(predicted_price)}} 
        ] }
        # Fetch matching houses from MongoDB
        houses = propertiescollection.find(query)
        house_list = []
        for house in houses:
            house_list.append({
                "image_url": house.get("image_urls", [None])[0],
                "owner_name": house.get("Ownername", 'N/A'),
                "owner_email": house.get("Owneremail", 'N/A'),
                "purpose": house.get("purpose", 'N/A'),
                "country": house.get("country", 'N/A'),
                "state": house.get("state", 'N/A'),
                "city": house.get("city", 'N/A'),
                "bedrooms": house.get("bedrooms", 'N/A'),
                "bathrooms": house.get("bathrooms", 'N/A'),
                "balcony": house.get("balcony", 'N/A'),
                "area": house.get("area", 'N/A'),
                "price_from": house.get("pricefrom", 'N/A'),
                "price_to": house.get("priceto", 'N/A'),
                "description": house.get("description", 'N/A'),
                "product_id": str(house.get("_id", 'N/A'))  # Convert ObjectId to string
            })

        return jsonify({
            'result': f'₹{predicted_price}',
            'houses': house_list
        })

    return render_template('predict.html')

@app.route('/history')
def history():
    # Fetch all prediction history from MongoDB
    history_data = db.prediction_history.find().sort('timestamp', -1)  # Sort by timestamp (most recent first)
    
    # Format the data to display
    history_list = []
    for record in history_data:
        history_list.append({
            "total_area": record.get('total_area'),
            "price_per_sqft": record.get('price_per_sqft'),
            "total_rooms": record.get('total_rooms'),
            "balcony": record.get('balcony'),
            "city": record.get('city'),
            "property_type": record.get('property_type'),
            "bhk": record.get('bhk'),
            "predicted_price": record.get('predicted_price'),
            "timestamp": record.get('timestamp').strftime('%Y-%m-%d %H:%M:%S')  # Format timestamp
        })
    return render_template('history.html', history_list=history_list)    
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    try:
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    except FileNotFoundError:
        abort(404)
@app.route('/logout')
def logout():
    session.pop('email', None)
    return redirect(url_for('get_email'))

@app.route('/adminlogout')
def adminlogout():
    session.pop('admin_ID', None)
    return redirect(url_for('admin'))










@app.route('/forgot_password', methods=['POST'])
def forgot_password():
    email = request.json.get('email')
    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400

    # Check if the email exists in the database
    user = collection.find_one({'email': email})
    if not user:
        return jsonify({'success': False, 'message': 'Email not found'}), 400

    otp = generate_otp()
    otps[email] = otp  # Store OTP

    # Send OTP to the user's email
    msg = Message('Password Reset OTP', sender='jyothsnameduri9999@gmail.com', recipients=[email])
    msg.body = f'Your OTP to reset password is {otp}'
    try:
        mail.send(msg)
        return jsonify({'success': True, 'message': 'OTP sent to your email'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/reset_password', methods=['POST'])
def reset_password():
    email = request.json.get('email')
    otp = request.json.get('otp')
    new_password = request.json.get('new_password')

    if not email or not otp or not new_password:
        return jsonify({'success': False, 'message': 'Email, OTP, and new password are required'}), 400

    # Verify OTP
    if otps.get(email) != otp:
        return jsonify({'success': False, 'message': 'Invalid OTP'}), 400

    # Find the user in the database
    user = collection.find_one({'email': email})
    if not user:
        return jsonify({'success': False, 'message': 'Email not found'}), 400

    # Update the password
    collection.update_one({'email': email}, {'$set': {'password': new_password}})

    # Clear OTP after successful reset
    del otps[email]

    return jsonify({'success': True, 'message': 'Password reset successfully'})

if __name__ == '__main__':
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)