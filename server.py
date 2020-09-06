from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin
from cryptography.fernet import Fernet
from werkzeug.utils import secure_filename
from flask import render_template
import pymongo
import functools
import datetime
import uuid
import random
import smtplib
import os
from bson import json_util, ObjectId
import bz2
import json
import requests
from flask import send_from_directory
import base64

MONGO_CONN_STRING = "mongodb://localhost:27017/"

app = Flask(__name__,static_folder="/srv/cloudexp/production",static_url_path='')
#app = Flask(__name__,static_folder="/home/thor/Desktop/Page/cloudexp/production/",static_url_path='')
cors = CORS(app, resources={r"/*": {"origins": "*"}})

app.secret_key = os.urandom(12)
key = b"pRmgMa8T0INjEAfksaq2aafzoZXEuwKI7wDe4c1F8AY="


class JSONEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, ObjectId):
            return str(o)
        return json.JSONEncoder.default(self, o)

def encryptPassword(password):
    cipher_suite = Fernet(key)

    ciphered_text = cipher_suite.encrypt(
        password.encode("utf-8")
    )  # required to be bytes
    ciphered_text = ciphered_text.decode("utf-8")
    print(ciphered_text)

    return ciphered_text


def decryptPassword(ciphered_text):
    cipher_suite = Fernet(key)

    unciphered_text = cipher_suite.decrypt(ciphered_text.encode("utf-8")).decode(
        "utf-8"
    )
    print(unciphered_text)

    return unciphered_text


def checkAuthenticated(func):
    @functools.wraps(func)
    def authentication():
        # print("HEADERS", request.headers.get('Authorization', 0))
        if request.headers.get("Authorization", 0) == 0:
            return jsonify({"result": "invalid request"})
        else:
            _uuid = request.headers["Authorization"]
            client = pymongo.MongoClient(MONGO_CONN_STRING)
            db = client["cloudexp"]
            posts = db.users
            userdata = posts.find_one({"uuid": _uuid})
            print("userdata", userdata)
            if userdata is not None:
                return func(userdata["_id"])
            else:
                return jsonify({"result": "authentication failed"})
    return authentication


@app.route('/',methods = ['GET'])
def openinterface():
    return send_from_directory(app.static_folder, 'index.html')


@app.route("/signin", methods=["POST"])
def signin():
    if request.method == "POST":
        client = pymongo.MongoClient(MONGO_CONN_STRING)
        db = client["cloudexp"]
        # print("post received")
        data = request.get_json()
        posts = db.users
        empid = data["empid"].replace(" ", "")

        # print("aa", data['adminconsole'])
        # print("aa", data['email'])
        userdata = posts.find_one({"empid": empid})
        print(userdata)

        if userdata is None:
            return jsonify({"result": "User Not Available Please Sign up"})
        elif (
            userdata is not None
            and decryptPassword(userdata["password"]) == data["password"]
        ):
            # print("aa", data['adminconsole'])
            # print("bb", userdata['adminconsole'])
            if (
                userdata["adminconsole"] == "true"
            ) or userdata["adminconsole"] == "false":
                myquery = {"empid": empid}
                update = {"$set": {}}
                _uuid = uuid.uuid4().hex
                update["$set"]["uuid"] = _uuid
                # print("myquery", myquery)
                # print("update", update)
                out = posts.update_one(myquery, update)
                print(userdata)
                return jsonify(
                    {
                        "result": "Sign in Successfully",
                        "uuid": _uuid,
                        "userid": str(userdata["_id"]),
                        "adminconsole": userdata["adminconsole"]
                    }
                )
            else:
                return jsonify({"result": "No Admin permission"})
        else:
            return jsonify({"result": "Please Enter the correct Password"})

    else:
        return "Invalid Request"


@app.route("/signup", methods=["POST"])
def signup():
    if request.method == "POST":
        client = pymongo.MongoClient(MONGO_CONN_STRING)
        db = client["cloudexp"]
        print("post received")
        data = request.get_json()
        posts = db.users
        empid = data["empid"].replace(" ", "")
        data["password"] = encryptPassword(data["password"])
        # print(emailid)
        query = {"empid": empid}
        isavailable = posts.find_one(query)
        # print("isavailable", isavailable)

        if isavailable is None:
            data["empid"] = empid
            data["created_at"] = datetime.datetime.now()
            data["adminconsole"] = "false"
            token = uuid.uuid4().hex
            result = posts.insert_one(data)
            return jsonify({"result": "Sign up successfull"})
        else:
            return jsonify({"result": "Emp Id Already Exist"})
    else:
        return "Invalid Request"


@app.route("/resetpassword", methods=["POST"])
def resetpassword():
    if request.method == "POST":
        client = pymongo.MongoClient(MONGO_CONN_STRING)
        db = client["cloudexp"]
        posts = db.tickets
        fetch = db.users
        data = request.get_json()
        print(data, "data")
        query = {"empid": data['empid']}
        fetched_data = fetch.find_one(query)
        if fetched_data is None:
            return jsonify({"result": "Emp Id not Exists"})
        else:
            data['userid'] = fetched_data['_id']
            data['email'] = fetched_data['email']
            data['phone'] = fetched_data['phone']
            data['approved'] = 0
            data["created_at"] = datetime.datetime.now()
            data["updated_at"] = datetime.datetime.now()
            insert = posts.insert_one(data)
            if insert is not None:
                return jsonify({"result": "ticket raised successfully"})
            else:
                return jsonify({"result": "try again"})
        
        
@app.route("/tickets", methods=["GET"])
@checkAuthenticated
def gettickect(_id):
    client = pymongo.MongoClient(MONGO_CONN_STRING)
    db = client["cloudexp"]
    fetch = db.tickets
    query = {'approved': 0}
    fetched_data = fetch.find(query)
    json_docs = []
    for doc in fetched_data:
        json_doc = json.dumps(doc, default=json_util.default)
        json_docs.append(json_doc)
    response = {'code': 0, 'results': JSONEncoder().encode(json_docs)}       
    return jsonify(response)

@app.route("/approve", methods=["PUT"])
@checkAuthenticated
def approve(_id):
    client = pymongo.MongoClient(MONGO_CONN_STRING)
    db = client["cloudexp"]
    fetch = db.tickets
    user = db.users
    query = {"userid": ObjectId(request.args['id'])}
    u_query = {"_id": ObjectId(request.args['id'])}
    update = {"$set": {}}
    update["$set"]["approved"] = 1
    update["$set"]["updated_at"] = datetime.datetime.now()
    fetch.update_one(query, update)
    u_update = {"$set": {}}
    u_update["$set"]["password"] = encryptPassword("Tcs#1234")
    user.update_one(u_query, u_update)
    return jsonify({"result": "Approved"})

@app.route("/decline", methods=["PUT"])
@checkAuthenticated
def decline(_id):
    client = pymongo.MongoClient(MONGO_CONN_STRING)
    db = client["cloudexp"]
    fetch = db.tickets
    query = {"userid": ObjectId(request.args['id'])}
    update = {"$set": {}}
    update["$set"]["approved"] = 2
    update["$set"]["updated_at"] = datetime.datetime.now()
    fetch.update_one(query, update)
    return jsonify({"result": "Declined"})
    

@app.route("/signout", methods=["GET"])
@checkAuthenticated
def signout(_id):
    if request.method == "GET":
        client = pymongo.MongoClient(MONGO_CONN_STRING)
        db = client["cloudexp"]
        posts = db.users
        myquery = {"_id": _id}
        update = {"$set": {}}
        _uuid = uuid.uuid4().hex
        update["$set"]["uuid"] = _uuid
        posts.update_one(myquery, update)
        return jsonify({"result": "log out successfull"})
    else:
        return "Invalid Request"




if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
