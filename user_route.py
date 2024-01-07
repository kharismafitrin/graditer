import tensorflow as tf
from flask import Flask, request, jsonify, Blueprint, redirect, url_for, render_template, flash
from config import mongo, db_user, db_essay, db_sw
from model_aes import preprocess, f1
from keras.preprocessing.text import Tokenizer
from keras.preprocessing.sequence import pad_sequences
from keras import backend as K
import keras
from keras.models import load_model
from bson import ObjectId
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from config import fs
from bson.binary import Binary
from io import BytesIO

user_blueprint = Blueprint('users', __name__)

# crud db users

def user_inc_index():
    user = db_user.find_one_and_update(
        {"_id": "user_id"},
        {"$inc": {"dump_index": 1}},
        upsert=True,
        return_document=True,
    )
    return str(user["dump_index"])

def essay_inc_index():
    essay = db_essay.find_one_and_update(
        {"_id": "essay_id"},
        {"$inc": {"dump_index": 1}},
        upsert=True,
        return_document=True,
    )
    return str(essay["dump_index"])

def convert_to_tens(predicted_scores):
    # predicted_scores: list atau array dari nilai predicted_score

    # Pastikan predicted_scores tidak kosong
    if not predicted_scores:
        return None  # Atau nilai default sesuai kebutuhan Anda

    # Fungsi untuk mengambil nilai float dari string yang berformat '[[0.10502023]]'
    def extract_float_value(s):
        try:
            return float(s.replace("[[", "").replace("]]", ""))
        except ValueError:
            return None

    # Konversi nilai prediksi menjadi nilai puluhan
    predictions_tens = [round(extract_float_value(score) * 100) for score in predicted_scores]

    # Hapus nilai yang tidak bisa diubah menjadi float
    predictions_tens = [score for score in predictions_tens if score is not None]

    # Pastikan predicted_scores memiliki nilai yang bisa diolah
    if not predictions_tens:
        return None

    # Jumlahkan nilai prediksi
    total_predictions = sum(predictions_tens)

    # Bagi total nilai prediksi dengan jumlah pertanyaan
    average_predictions = total_predictions / len(predicted_scores)

    # Konversi nilai hasil rata-rata menjadi nilai puluhan
    average_predictions_tens = round(average_predictions)

    return average_predictions_tens

@user_blueprint.route('/create_user', methods=['GET', 'POST'])
def create_user():
    _json = request.json
    # _name = _json['name']
    _email = _json['email']
    _password = _json['password']
    # _npm = _json['npm']
    # _role = _json['role']
    
    if _email and _password and request.method == 'POST':
        _hashed_password = generate_password_hash(_password)
        _index = str(user_inc_index())
            
        # id = db_user.insert_one({'index':_index, 'name' : _name, 'email':_email, 'password' : _hashed_password, 'npm' : _npm, 'role':_role})
        id = db_user.insert_one({'index':_index, 'email':_email, 'password' : _hashed_password})
        
        resp = jsonify("User added succesfully")
        resp.status_code = 200
        
        return resp
    else:
        return not_found()
    
@user_blueprint.errorhandler(404)
def not_found(error = None):
    message = {
        'status' : 404,
        'message' : 'Not Found' + request.url
    }
    resp = jsonify(message)
    resp.status_code = 404
    return resp

# Route to create user collection and insert new data
@user_blueprint.route('/users', methods=['GET'])
def api_users():
    user_collection = db_user

    # Fetch all users from the collection
    users_cursor = user_collection.find()

    # Convert the cursor to a list of dictionaries
    users = list(users_cursor)

    # Convert ObjectId to string for JSON serialization
    for user in users:
        user['_id'] = str(user['_id'])

    # Count the documents in the "users" collection
    user_count = user_collection.count_documents({})

    response_data = {'user_count': user_count, 'users': users}
    # Return a JSON response containing the inserted users
    return jsonify(response_data)

@user_blueprint.route('/delete/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    db_user.delete_one({'_id': ObjectId(user_id)})
    resp = jsonify("User deleted successfully")
    resp.status_code = 200
    return resp

@user_blueprint.route('/update/<user_id>', methods=['PUT'])
def update_user(user_id):
    try:
        _id = user_id
        _json = request.json

        # Pastikan _json bukan None dan _json adalah dictionary
        if _json and isinstance(_json, dict):
            update_fields = {}  # Inisialisasi dictionary untuk bidang yang akan diupdate

            # Cek apakah bidang-bidang yang akan diupdate ada dalam _json
            if 'name' in _json:
                update_fields['name'] = _json['name']

            if 'email' in _json:
                update_fields['email'] = _json['email']

            if 'password' in _json:
                update_fields['password'] = generate_password_hash(_json['password'])

            if 'npm' in _json:
                update_fields['npm'] = _json['npm']

            # Perbarui dokumen menggunakan operator $set
            db_user.update_one({'_id': ObjectId(_id)}, {'$set': update_fields})

            resp = jsonify("User updated successfully")
            resp.status_code = 200

            return resp
        else:
            return jsonify({'error': 'Invalid JSON data'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@user_blueprint.route('/admin/add/<index>')
def tambahEsai(index):
    try:
        user = db_user.find_one({'index': index})
        
        if user:
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return render_template('admin/tambahEsai.html', user=user, user_name=user_name)
        else:
            return jsonify({'error' : 'Page not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500
    
# @user_blueprint.route('/users/<user_id>')
# def get_user_by_id(user_id):
#     try:
#         user_object_id = ObjectId(user_id)
#         user = db_user.find_one({'_id': user_object_id})

#         if user:
#             user['_id'] = str(user['_id'])
#             return jsonify(user)
#         else:
#             return jsonify({'error' : 'User not found'}), 404
#     except Exception as e:
#         # Handle any exceptions that may occur during the process
#         return jsonify({'error': str(e)}), 500
    
@user_blueprint.route('/users/<index>')
def get_user_by_index(index):
    try:
        user = db_user.find_one({'index': index})
        
        if user:
            # Convert the index back to a string in the response
            user['_id'] = str(user['_id'])
            user['index'] = str(user['index'])
            return jsonify(user)
        else:
            return jsonify({'error': 'User not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        print(f"Error: {str(e)}")
        return jsonify({'error': str(e)}), 500

    
@user_blueprint.route('/register', methods=['GET', 'POST'])
def register():
    # Get user input from the form
    email = request.form.get('email')
    password = request.form.get('password')
    confirm_password = request.form.get('confirm_password')
    role = 'user'
    
    if email and password and confirm_password and request.method == 'POST':
        existing_user = db_user.find_one({'email': email})
        
        if existing_user:
            flash('Email is already registered. Please use a different email.', 'danger')
            return render_template('register.html')
        
        if password != confirm_password:
            flash('Make sure password and confirm password are same.', 'danger')
            return render_template('register.html')
    
        _hashed_password = generate_password_hash(password)
        _index = str(user_inc_index())
        
        db_user.insert_one({'index':_index,'email':email, 'password' : _hashed_password, 'role':role, 'npm':None, 'name':None})
       
        # Flash a success message
        flash('Registration successful!', 'success')
        
        # Redirect to a success page (you can customize this)
        return render_template('register.html')
    # Render the registration form for GET requests
    return render_template('register.html')

@user_blueprint.route('/', methods=['GET', 'POST'])
def login():
    email = request.form.get('email')
    password = request.form.get('password')
    
    if email and password and request.method == 'POST':
        user = db_user.find_one({'email': email})
        
        if user and check_password_hash(user['password'], password):
            # Authentication successful, set a session variable or perform other tasks
            flash('Login successful!', 'success')
            if 'role' in user:
                if user['role'] == 'admin':
                    # return redirect(url_for('users.profile_admin_by_id', user_id=str(user['_id'])))
                    return redirect(url_for('users.profile_admin_by_index', index=user['index']))
                elif user['role'] == 'user':
                    return redirect(url_for('users.profile_user_by_index', index=user['index']))
            return redirect(url_for('profile_user_by_id', user_id=str(user['_id'])))  # Redirect to the dashboard or another page
        else:
            flash('Invalid email or password', 'error')
            
    return render_template('login.html')

# @user_blueprint.route('/user/<user_id>')
# def profile_user_by_id(user_id):
#     try:
#         user_object_id = ObjectId(user_id)
#         user = db_user.find_one({'_id': user_object_id})

#         if user:
#             user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
#             return render_template('user.html', user_id=str(user['_id']), user_email=user['email'], user_name=user_name)
#         else:
#             return jsonify({'error' : 'User not found'}), 404
#     except Exception as e:
#         # Handle any exceptions that may occur during the process
#         return jsonify({'error': str(e)}), 500
    
@user_blueprint.route('/user/<index>')
def profile_user_by_index(index):
    try:
        exception_essay_id = 'essay_id'
        user = db_user.find_one({'index': index})
        user_essay_do = db_sw.find({'user_index': index})
        index_essay_and_predicted_score = []
        index_essay_none = []

        for doc in user_essay_do:
            index_essay = doc['index_essay']
            answer_data = doc.get('answer_data', [])
            for entry in answer_data:
                predicted_score = entry.get('predicted_score')
                if predicted_score is None and index_essay not in index_essay_none:
                    index_essay_none.append(index_essay)
                else:
                    index_essay_and_predicted_score.append({'index_essay': index_essay, 'predicted_score': predicted_score})
            
        # print("index_essay_and_predicted_score" , index_essay_and_predicted_score)
        # print("index_essay_none" , index_essay_none)
       
        essay_do = db_sw.find({'user_index' : index})
        index_essay_do = [doc['index_essay'] for doc in essay_do]
        
            
        essays_data = db_essay.find({
            '_id': {'$ne': exception_essay_id},
            'index': {'$in': index_essay_do}
        })
        
        # print("index essay do", index_essay_do)
        
        index_essay_none = set(index_essay_none)  # Assuming '9' is in index_essay_none
        index_essay_do = set(index_essay_do)

        # Find the elements that are in index_essay_do but not in index_essay_none
        difference = index_essay_do - index_essay_none

        # Convert the result back to a list if needed
        difference_list = list(difference)

        # print(difference_list)
        
        if user:
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return render_template('user.html', user=user, user_name=user_name, essays=essays_data, essay_done=difference_list)
        else:
            return jsonify({'error' : 'User not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500
    
# @user_blueprint.route('/admin/<user_id>')
# def profile_admin_by_id(user_id):
#     try:
#         user_object_id = ObjectId(user_id)
#         user = db_user.find_one({'_id': user_object_id})

#         if user:
#             user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
#             return render_template('/admin/admin.html', user_id=str(user['_id']), user_email=user['email'], user_name=user_name)
#         else:
#             return jsonify({'error' : 'Admin not found'}), 404
#     except Exception as e:
#         # Handle any exceptions that may occur during the process
#         return jsonify({'error': str(e)}), 500

@user_blueprint.route('/admin/<index>')
def profile_admin_by_index(index):
    try:
        user = db_user.find_one({'index': index})

        if user:
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return render_template('/admin/admin.html', user=user, user_name=user_name)
        else:
            return jsonify({'error' : 'Admin not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500
    
# @user_blueprint.route('/user/intro/<user_id>')
# def introSoal(user_id):
#     try:
#         user_object_id = ObjectId(user_id)
#         user = db_user.find_one({'_id': user_object_id})

#         if user:
#             user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
#             return render_template('introSoal.html', user_id=str(user['_id']), user_email=user['email'], user_name=user_name)
#         else:
#             return jsonify({'error' : 'Page not found'}), 404
#     except Exception as e:
#         # Handle any exceptions that may occur during the process
#         return jsonify({'error': str(e)}), 500
    

@user_blueprint.route('/user/intro/<index>/<index_soal>')
def introSoal(index, index_soal):
    try:
        user = db_user.find_one({'index': index})
        essay = db_essay.find_one({'index':index_soal})

        if user:
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return render_template('introSoal.html', user=user, user_name=user_name, essay=essay)
        else:
            return jsonify({'error' : 'Page not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500
    
@user_blueprint.route('/admin/adminEsai/<index>')
def adminEsai(index):
    try:
        exception_essay_id = 'essay_id'
        essays_data = db_essay.find({'_id': {'$ne': exception_essay_id}})
        user = db_user.find_one({'index': index})

        if essays_data and user:
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            essays = list(essays_data)
            return render_template('admin/adminEsai.html', essays=essays, user=user, user_name=user_name)
        else:
            return jsonify({'error': 'Essay data not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500
    
@user_blueprint.route('/admin/adminPengguna/<index>')
def adminPengguna(index):
    try:
        exception_user_id = 'user_id'
        user_data = db_user.find({'_id': {'$ne': exception_user_id}})
        user = db_user.find_one({'index': index})

        if user_data and user:
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            users = list(user_data)
            return render_template('admin/adminPengguna.html', users=users, user=user, user_name=user_name)
        else:
            return jsonify({'error': 'Essay data not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500
    
@user_blueprint.route('/user/soal/<index>/<index_soal>')
def kerjakanSoal(index, index_soal):
    try:
        user = db_user.find_one({'index': index})
        essay = db_essay.find_one({'index':index_soal})
        questions = essay.get('questions', [])

        if user:
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return render_template('kerjakanSoal.html', user=user, user_name=user_name, essay=essay, questions=questions)
        else:
            return jsonify({'error' : 'Page not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500




@user_blueprint.route('/user/hasil/<index>/<index_soal>', methods=['GET', 'POST'])
def result(index, index_soal):
    try:
        user = db_user.find_one({'index': index})
        essay = db_essay.find_one({'index':index_soal})
        questions = essay.get('questions', [])
        user_essay_done = db_sw.find({'user_index' : index})
        essay_done = [entry.get('index_essay') for entry in user_essay_done]
        # Assuming model is stored in GridFS and retrieved as 'model' from fs.get(model_file_id)
        max_length = essay['max_length']
        model_file_id = ObjectId(essay['model_file_id'])
        model_data = fs.get(model_file_id)
        model_bytesio = BytesIO(model_data.read())

        # Save the in-memory file to a temporary file
        temp_model_file_path = "temp_model.h5"
        with open(temp_model_file_path, "wb") as temp_file:
            temp_file.write(model_bytesio.read())

        # Load the model with custom metric
        with keras.utils.custom_object_scope({'f1': f1}):
            global model
            model = load_model(temp_model_file_path)
        
        num = 1
        
        if user and request.method == 'POST':
            answer_data_list = []

            for q in questions:
                question_id = num
                answer = request.form.get(f'answer_{q["question_id"]}')
                num += 1

                processed_answer = preprocess(answer)
                maxlen = max_length

                tokenizer = Tokenizer()
                token_1 = tokenizer.fit_on_texts([processed_answer])
                essay_tokens_1 = tokenizer.texts_to_sequences([processed_answer])

                essay_tokens_padded_1 = pad_sequences(essay_tokens_1, maxlen=maxlen)

                result_as_str = str(model.predict(essay_tokens_padded_1))

                answer_data = {
                    'question_id': question_id,
                    'answer': answer,
                    'predicted_score': result_as_str
                }

                answer_data_list.append(answer_data)

            
            student_work = {
                # 'index_essay': essay['index'],
                # 'user_index': user['index'],
                # 'name': user['name'],
                # 'npm': user['npm'],
                'answer_data': answer_data_list
            }

            # Insert the entire student work data into the database
            db_sw.update_one({'user_index':index, 'index_essay':index_soal}, {'$set': student_work})
            temp = db_sw.find_one({'user_index': index, 'index_essay': index_soal})
            result = temp.get('answer_data', [])
            predicted_scores = [item.get('predicted_score', 0) for item in result]
            result_in_tens = convert_to_tens(predicted_scores)
            
            db_sw.update_one(
                {'user_index': index, 'index_essay': index_soal},
                {'$set': {'result_in_tens': result_in_tens}}
            )
            
            temp = db_sw.find_one({'user_index': index, 'index_essay': index_soal})
            
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0] 
            return render_template('result.html', user=user, user_name=user_name, essay=essay, temp=temp)
        
        elif user and index_soal in essay_done:
            temp = db_sw.find_one({'user_index': index, 'index_essay': index_soal})
            
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            # return jsonify({'error' : 'Page not found'}), 404
            return render_template('result.html', user=user, user_name=user_name, essay=essay, temp=temp)
        else:
            exception_essay_id = 'essay_id'
            essays = db_essay.find({'_id': {'$ne': exception_essay_id}})
            flash('Maaf, tugas belum dikerjakan. Kerjakan tugas sekarang!', 'error')
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return render_template('user.html', user=user, user_name=user_name, essays=essays, essay_done=essay_done)
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500
    
@user_blueprint.route('/admin/adminEsai/<index>', methods=['GET', 'POST'])
def create_essays(index):
    exception_essay_id = 'essay_id'
    essays_data = db_essay.find({'_id': {'$ne': exception_essay_id}})
    user = db_user.find_one({'index': index})
    
    # Accessing form data
    if user and essays_data and request.method == 'POST' :
        user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
        
        mata_pelajaran = str(request.form.get('mata_pelajaran'))
        title = str(request.form.get('title'))
        total_time = request.form.get('total-time')
        form_file = request.files['formFile']
        questions_texts = request.form.getlist('questions[]')
        question_id = 1  # Initialize question_id to 1
        processed_questions = []
        _index = str(essay_inc_index())
        _max=int(request.form.get('max_length'))
            
        for question_text in questions_texts:
            # Incremental processing logic based on question_id and question_text
            processed_question = {
                'question_id': question_id,
                'question_text': question_text
                # Add more fields as needed
            }
            processed_questions.append(processed_question)

            # Increment question_id
            question_id += 1
        
        try:
            filename = secure_filename(form_file.filename)
            file_content = form_file.read()
            file_id = fs.put(file_content, filename=filename)
                
            essay_data = {
                'mata_pelajaran': mata_pelajaran,
                'title': title,
                'total_time': total_time,
                'questions': processed_questions,
                'model_file_id': str(file_id),
                'index':_index,
                'max_length':_max
            }

            if mata_pelajaran and title and total_time and questions_texts and max:
                db_essay.insert_one(essay_data)
                essays = list(essays_data)
                return render_template('admin/adminEsai.html', essays=essays, user=user, user_name=user_name)
            else:
                # Display an alert or return a JSON response with an error message
                flash('Some required data is missing or empty', 'error'), 400  
        except FileNotFoundError:
            flash('Missing file', 'error')
            return render_template('admin/tambahEsai.html', user=user, user_name=user_name)

    user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
    return render_template('admin/tambahEsai.html', user=user, user_name=user_name)
    

@user_blueprint.route('/admin/detail/<index>/<index_soal>')
def detail_esai(index, index_soal):
    try:
        # exception_essay = {'_id': 'essay_id'}
        exception_user_id = 'user_id'
        user = db_user.find_one({'index': index, '_id': {'$ne': exception_user_id}})
        essay = db_essay.find_one({'index': index_soal})
        model_file_id = ObjectId(essay['model_file_id'])
        model = fs.get(model_file_id)
        model_name = model.filename
        # answer_sw = [doc.get('answer_data', {}) for doc in student_work]
        questions = essay.get('questions', [])
        # question_texts = [question.get('question_text', '') for question in questions]
        # Fetch registered students for the specific essay
        registered_students = db_sw.find({'index_essay': str(index_soal)})
        registered_user_indexes = [student['user_index'] for student in registered_students]
        
        student_work = db_sw.find({
            'index_essay': index_soal,
            'user_index': {'$in': registered_user_indexes}
        })
        
        # temp_cursor = db_sw.find({
        #     'index_essay': index_soal,
        #     'user_index': {'$in': registered_user_indexes}
        # })
        # temp_data = list(temp_cursor)
        
        # list_answer_data = []
        # for t in temp_data:
        #     result = t.get('answer_data', [])
        #     list_answer_data.append(result)
            
        # for l in list_answer_data
            
        # first_temp = temp_data[0]

        # # Retrieve 'answer_data' from the first element
        # result = first_temp.get('answer_data', [])

        # # Retrieve 'predicted_score' from 'answer_data'
        # predicted_scores = [item.get('predicted_score', 0) for item in result]

        # # Convert predicted_scores to tens using the convert_to_tens function
        # result_in_tens = convert_to_tens(predicted_scores)
        # print(registered_user_indexes)
        
        users_not_in_sw = db_user.find({'index': {'$nin': registered_user_indexes}, '_id': {'$ne': exception_user_id}})
        
        # for doc in user_essay_do:
        #     index_essay = doc['index_essay']
        #     answer_data = doc.get('answer_data', [])
        #     for entry in answer_data:
        #         predicted_score = entry.get('predicted_score')
        #         if predicted_score is None and index_essay not in index_essay_none:
        #             index_essay_none.append(index_essay)
        #         else:
        #             index_essay_and_predicted_score.append({'index_essay': index_essay, 'predicted_score': predicted_score})
        
        # answer_data = [student['answer_data'] for student in student_work]
        # print(answer_data)
        # for doc in student_work:
        #     answer_data.append(doc.get('answer_data', []))
        # for user in users_not_in_sw:
        #     print(user['index'])

        if user and users_not_in_sw:
            # essay_json = json_util.dumps(essay)
            # selected_user_indexes = request.form.getlist('selectedUsers')
            # selected_users = [user for user in available_students if user['index'] in selected_user_indexes]
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return render_template('admin/detailEsai.html', user=user, user_name=user_name, essay=essay, model_name=model_name, student_work=student_work, questions=questions, nisw=users_not_in_sw)
            # return render_template('admin/detailEsai.html', user=user, user_name=user_name, essay=essay)
        else:
            return jsonify({'error' : 'Page not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500
    
    
@user_blueprint.route('/admin/edit/<index>/<index_soal>', methods=['GET', 'POST'])
def edit_esai(index, index_soal):
    try:
        exception_essay = {'_id': 'essay_id'}
        exception_user_id = 'user_id'
        user = db_user.find_one({'index': index, '_id': {'$ne': exception_user_id}})
        essay = db_essay.find_one({'index': index_soal, '_id': {'$ne': exception_essay}} )
        model_file_id = ObjectId(essay['model_file_id'])
        # if essay and essay['model_file_id']:
        #     model_file_id = ObjectId(essay['model_file_id'])
        # else:
        #     # Handle the case where essay or essay['model_file_id'] is None
        #     model_file_id = None  # Or assign a default value or handle the case accordingly
        
        model = fs.get(model_file_id)
        model_name = model.filename  
        print(model_name)  

        if user and request.method == 'POST':
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
                
            mata_pelajaran = str(request.form.get('mata_pelajaran'))
            title = str(request.form.get('title'))
            total_time = request.form.get('total-time')
            form_file = request.files['formFile']
            questions_texts = request.form.getlist('questions[]')
            question_id = 1  # Initialize question_id to 1
            processed_questions = []
            # _index = str(essay_inc_index())
            _max=int(request.form.get('max_length'))
                
            for question_text in questions_texts:
                # Incremental processing logic based on question_id and question_text
                processed_question = {
                    'question_id': question_id,
                    'question_text': question_text
                    # Add more fields as needed
                }
                processed_questions.append(processed_question)
                # Increment question_id
                question_id += 1
            
            print(processed_questions)
            filename = secure_filename(form_file.filename)
            file_content = form_file.read()
            file_id = fs.put(file_content, filename=filename)
                    
            essay_data = {
                'mata_pelajaran': mata_pelajaran,
                'title': title,
                'total_time': total_time,
                'questions': processed_questions,
                'model_file_id': str(file_id),
                'max_length':_max
            }

            if mata_pelajaran and title and total_time and questions_texts and max and form_file:
                db_essay.update_one({'index':index_soal},{'$set' : essay_data})
                essays = db_essay.find_one({'index' : index_soal, '_id': {'$ne': exception_essay}})
                essays = list(essays)
                return redirect(url_for('users.adminEsai', index=user['index']))
            else:
                # Display an alert or return a JSON response with an error message
                flash('Some required data is missing or empty', 'error'), 400      
    except FileNotFoundError:
        flash('Missing file', 'error')
    
    user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
    return render_template('admin/editEsai.html', user=user, user_name=user_name, essay=essay, model_name = model_name)
    
    # user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]  
    # return redirect(url_for('users.edit_esai', index=user['index'], index_soal=essay['index']))

@user_blueprint.route('/admin/adminEsai/<index>/<index_soal>', methods=['GET','DELETE'])
def delete_essay(index, index_soal):
    try:
        # exception_essay_id = 'essay_id'
        user = db_user.find_one({'index': index})
        # essays = db_essay.find_one({'index': index_soal, '_id': {'$ne': exception_essay_id}})
        # model_file_id = ObjectId(essay['model_file_id'])
        # model = fs.get(model_file_id)
        # model_name = model.filename
        # users = db_user.find()
        
        # questions = essay.get('questions', [])
        # question_texts = [question.get('question_text', '') for question in questions]
        
        # registered_students = db_sw.find({'index_essay': index_soal})
        # Filter the users to exclude those who are already registered
        # available_students = [user for user in users if user['index'] not in [student['user_index'] for student in registered_students]]
        
        if user and request.method == 'DELETE':
            index_soal = request.view_args.get('index_soal')
            db_essay.delete_one({'index': index_soal})
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return redirect(url_for('users.adminEsai', index=user['index'], user_name=user_name))
            # return render_template('admin/detailEsai.html', user_name=user_name, essay=essay, model_name=model_name, users=users, student_work=student_work, questions=questions)
        else:
            return jsonify({'error' : 'Page not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500

@user_blueprint.route('/admin/detail/<index>/<index_soal>', methods=['GET', 'POST', 'DELETE'])
def student_work_topic(index, index_soal):
    try:
        user = db_user.find_one({'index': index})
        essay = db_essay.find_one({'index': index_soal})
        model_file_id = ObjectId(essay['model_file_id'])
        model = fs.get(model_file_id)
        model_name = model.filename
        users = db_user.find()
        
        questions = essay.get('questions', [])
        
        # registered_students = db_sw.find({'index_essay': index_soal})
        # Filter the users to exclude those who are already registered
        # available_students = [user for user in users if user['index'] not in [student['user_index'] for student in registered_students]]
        
        if user and request.method == 'POST':
            # Handle the form submission here
            selected_user_data = []
            # selected_user_indexes = request.form.getlist('selectedUsers')
            # selected_users = [user for user in available_students if user['index'] in selected_user_indexes]

            selected_user_indexes = request.form.getlist('selectedUsers')
            for user_index in selected_user_indexes:
                selected_user = db_user.find_one({'index': user_index})
                if selected_user:
                    selected_user_data.append({
                        'index': selected_user['index'],
                        'name': selected_user.get('name', ''),
                        'npm': selected_user.get('npm', ''),
                    })

            answer_data_list = []
            
            for q in questions:
                answer_data = {
                    'question_id': q['question_id'],
                    'answer': None,
                    'predicted_score': None
                }
                answer_data_list.append(answer_data)
                
            for user_data in selected_user_data:
                npm_value = user_data.get('npm', 'default_npm_value')
                sw_data = {
                    'index_essay': essay['index'],
                    'user_index': user_data['index'],
                    'name' : user_data['name'],
                    'npm' : user_data['npm'] or npm_value,
                    'answer_data' : answer_data_list
                }
                db_sw.insert_one(sw_data)
            
            student_work = db_sw.find()
            # print(student_work)
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return render_template('admin/detailEsai.html', user_name=user_name, essay=essay, model_name=model_name, users=users, student_work=student_work, questions=questions)
        else:
            return jsonify({'error' : 'Page not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500
    
@user_blueprint.route('/admin/detail/<index>/<index_soal>/<user_index>', methods=['DELETE'])
def delete_sw(index, index_soal, user_index):
    try:
        user = db_user.find_one({'index': index})
        essay = db_essay.find_one({'index': index_soal})
        model_file_id = ObjectId(essay['model_file_id'])
        model = fs.get(model_file_id)
        model_name = model.filename
        users = db_user.find()
        
        questions = essay.get('questions', [])
        # question_texts = [question.get('question_text', '') for question in questions]
        
        # registered_students = db_sw.find({'index_essay': index_soal})
        # Filter the users to exclude those who are already registered
        # available_students = [user for user in users if user['index'] not in [student['user_index'] for student in registered_students]]
        
        if user and request.method == 'DELETE':
            user_index = request.view_args.get('user_index')
            db_sw.delete_one({'user_index': user_index})
            student_work = db_sw.find()
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return render_template('admin/detailEsai.html', user_name=user_name, essay=essay, model_name=model_name, users=users, student_work=student_work, questions=questions)
        else:
            return jsonify({'error' : 'Page not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500
    
@user_blueprint.route('/user/edit/<index>', methods=['GET', 'POST'])
def edit_profile(index):
    user = db_user.find_one({'index':index})
    user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
    
    if user and request.method == 'POST':
        password = str(request.form.get('password'))
        email = str(request.form.get('email'))
        name = str(request.form.get('name'))
        npm = str(request.form.get('npm'))

        # Mengambil data pengguna dari database
        existing_user_data = db_user.find_one({'index': index})

        if check_password_hash(existing_user_data['password'], password):
            # Jika sama, gunakan password yang ada di database
            temp_password = existing_user_data['password']
        else:
            # Jika berbeda dan password baru tidak kosong, hash password baru
            if password:
                hashed_password = generate_password_hash(password)
                temp_password = hashed_password
            else:
                # Jika password baru kosong, tetap gunakan password yang ada di database
                temp_password = existing_user_data['password']

        # Mengupdate data pengguna di database
        pengguna_data = {
            'email': email,
            'password': temp_password,
            'npm': npm,
            'name': name
        }

        db_user.update_one({'index': index}, {'$set': pengguna_data})
        return redirect(url_for('users.profile_user_by_index', index=user['index'], user_name=user_name))
    
    return render_template('edit_profile.html', user=user, user_name=user_name)

@user_blueprint.route('/admin/add_user/<index>', methods=['GET', 'POST'])
def tambahUser(index):
    user = db_user.find_one({'index':index})
    if user:
        user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
        return render_template('admin/tambahUser.html', user=user, user_name=user_name)
    else:
        return not_found()
    
@user_blueprint.route('/admin/tambah/<index>', methods=['GET', 'POST'])
def add_user(index):
    user = db_user.find_one({'index': index})
    user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
    
    if request.method == 'POST':
        email = str(request.form.get('email'))
        password = str(request.form.get('password'))
        name = str(request.form.get('name'))
        npm = str(request.form.get('npm'))
        role = 'user'
        
        existing_user = db_user.find_one({'email': email})
        if existing_user:
            flash('Email is already registered. Please use a different email.', 'danger')
            return render_template('admin/tambahUser.html', user=user, user_name=user_name)
            
        if user and email and password and name and npm and request.method == 'POST':
            _hashed_password = generate_password_hash(password)
            _index = str(user_inc_index())
            db_user.insert_one({'index': _index, 'email': email, 'password': _hashed_password, 'role': role, 'npm': npm, 'name': name})

            return redirect(url_for('users.adminPengguna', user=user, user_name=user_name, index=index))
        else:
            flash('Missing some information or field', 'error')

    return render_template('admin/tambahUser.html', user=user, user_name=user_name)

@user_blueprint.route('/admin/edit_pengguna/<index>/<index_user>', methods=['GET', 'POST'])
def edit_pengguna(index, index_user):
    user = db_user.find_one({'index':index})
    pengguna = db_user.find_one({'index':index_user})
    
    user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
    
    if user and pengguna and request.method == 'POST':
        password = str(request.form.get('password'))
        email = str(request.form.get('email'))
        name = str(request.form.get('name'))
        npm = str(request.form.get('npm'))

        # Mengambil data pengguna dari database
        existing_user_data = db_user.find_one({'index': index_user})

        # Memeriksa apakah password baru sama dengan password yang ada di database
        if check_password_hash(existing_user_data['password'], password):
            # Jika sama, gunakan password yang ada di database
            temp_password = existing_user_data['password']
        else:
            # Jika berbeda dan password baru tidak kosong, hash password baru
            if password:
                hashed_password = generate_password_hash(password)
                temp_password = hashed_password
            else:
                # Jika password baru kosong, tetap gunakan password yang ada di database
                temp_password = existing_user_data['password']

        # Mengupdate data pengguna di database
        pengguna_data = {
            'email': email,
            'password': temp_password,
            'npm': npm,
            'name': name
        }

        db_user.update_one({'index': index_user}, {'$set': pengguna_data})
        return redirect(url_for('users.adminPengguna', index=user['index'], user_name=user_name, pengguna=pengguna))

    
    # return redirect(url_for('users.adminPengguna', index=user['index'], user_name=user_name))
    return render_template('admin/editPengguna.html', user=user, user_name=user_name, pengguna=pengguna)

@user_blueprint.route('/admin/adminPengguna/<index>/<index_user>', methods=['GET', 'DELETE'])
def delete_pengguna(index, index_user):
    try:
        user = db_user.find_one({'index': index})
        exception_user_id = {'_id' : 'user_id'}
        users = db_user.find({'_id': {'$ne': exception_user_id}})
        
        if user and request.method == 'DELETE':
            index_user = request.view_args.get('index_user')
            db_user.delete_one({'index': index_user})
            user_name = user['name'] if 'name' in user and user['name'] is not None else user['email'].split('@')[0]
            return redirect(url_for('users.adminPengguna', index=user['index'], user_name=user_name, users=users))
            # return render_template('admin/detailEsai.html', user_name=user_name, essay=essay, model_name=model_name, users=users, student_work=student_work, questions=questions)
        else:
            return jsonify({'error' : 'Page not found'}), 404
    except Exception as e:
        # Handle any exceptions that may occur during the process
        return jsonify({'error': str(e)}), 500