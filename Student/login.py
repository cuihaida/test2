from flask import Flask, render_template
from flask import session
from flask import request, url_for, redirect
from flask import flash
import pymongo
import os
from elasticsearch import Elasticsearch
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)  # 设置secret_key
py_client = pymongo.MongoClient("mongodb://localhost:27008/")
py_db = py_client["test"]
py_collection = py_db["collection_1"]
es = Elasticsearch("127.0.0.1:9200")


# ---- es 输出结果验证 -----------
def foreach(res):
    ans = []
    doc = res['hits']['hits']
    if len(doc):
        for item in doc:
            # --- 使用高亮法进行查询
            if 'highlight' in item.keys():
                new_dict = {**item['_source'], **item['highlight']}
                ans.append(new_dict)
            # --- 没有声明查询高亮
            else:
                ans.append(item['_source'])
        return ans
    else:
        return None


# -------------- 登录验证 --------- #
def judge_login(username, password):
    my_query = {"username": username, "password": password}
    answer = py_collection.find_one(my_query)
    # 有这个人，可以进行登录
    if answer is not None:
        return True
    else:
        return False


# ----------- 注册验证 ------------ #
def judge_register(username, password, phone):
    my_query = {"username": username, "password": password, "phone": phone}
    answer = py_collection.find_one(my_query)
    # 有这个人了，不可以再注册了
    if answer is not None:
        return False
    else:
        return True


# -------- 获取集合中的所有的字段 --------- #
def get_collection_all_keys(collection):
    name_list = []  # 存放得到的字段值
    datas = collection.find({})
    for data in datas:
        for key in data.keys():
            if key not in name_list:
                name_list.append(key)
    return name_list


# ------------- 登录操作 ---------- #
@app.route("/")
def init():
    return render_template("login.html")


@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # 获取表单中的姓名和密码
        name = request.form.get("username")
        pwd = request.form.get("password")
        # 判断这个人是不是在数据库中
        answer = judge_login(name, pwd)
        if answer:
            flash("成功登录")
            session['username'] = name
            session['password'] = pwd
            return redirect(url_for("welcome"))
        else:
            flash("没有该账号，请先注册")
            return redirect(url_for("reg"))


# ------------- 注册操作 ---------------- #
@app.route("/reg", methods=['GET', 'POST'])
def reg():
    return render_template("register.html")


@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        # 获取表单中的姓名和密码
        name = request.form.get("username")
        pwd = request.form.get("password")
        school = request.form.get("school")
        phone = request.form.get("phone")
        work = request.form.get("work")
        age = request.form.get("age")
        print(name, pwd, phone)
        # 判断这个人是不是在数据库中
        answer = judge_register(name, pwd, phone)
        # 可以注册，写入数据库
        if answer:
            my_dict = {"username": name, "password": pwd, "school": school, "phone": phone, "work": work,
                       "age": int(age)}
            x = py_collection.insert_one(my_dict)  # 写入
            print(x.inserted_id)
            flash("注册成功")
            return redirect(url_for("welcome"))
        else:
            return redirect(url_for("init"))


# ----------------------- 添加操作 ------------- #
@app.route("/add")
def add():
    return render_template("add.html")


@app.route("/judgeAdd", methods=["POST", "GET"])
def judge():
    if request.method == 'POST':
        # 获取表单中的姓名和密码
        name = request.form.get("username")
        pwd = request.form.get("password")
        school = request.form.get("school")
        phone = request.form.get("phone")
        print(name, pwd, phone)
        # 判断这个人是不是在数据库中
        answer = judge_register(name, pwd, phone)
        # 可以添加，写入数据库
        if answer:
            my_dict = {"username": name, "password": pwd, "school": school, "phone": phone}
            x = py_collection.insert_one(my_dict)  # 写入
            print(x.inserted_id)
            flash("添加成功")
            return redirect(url_for("welcome"))
        else:
            flash("添加失败，已有该名学生")
            return redirect(url_for("welcome"))


# ------------- 主要操作页面 ----------- #
@app.route("/welcome")
def welcome():
    students = py_collection.find({})
    return render_template("welcome.html", students=students)


# -------------- 修改操作 ----------- #
@app.route("/alter/<user_name>", methods=["GET", "POST"])
def alter(user_name):
    student_name = user_name
    if request.method == "POST":
        # 获取表单中的姓名和密码
        name = request.form.get("username")
        pwd = request.form.get("password")
        school = request.form.get("school")
        phone = request.form.get("phone")
        work = request.form.get("work")
        age = request.form.get("age")
        print(name, pwd, school, phone)
        my_filter = {"username": student_name}
        new_doc = {"$set": {"username": name, "password": pwd, "school": school, "phone": phone, "work": work,
                            "age": int(age)}}
        py_collection.update_one(my_filter, new_doc)
        return redirect(url_for("welcome"))
    return render_template("alter.html")


# -------------- 删除操作 --------------- #
@app.route("/delete/<user_name>")
def delete(user_name):
    student_name = user_name
    print(student_name)
    my_filter = {"username": str(student_name)}
    py_collection.delete_one(my_filter)
    return redirect(url_for("welcome"))


# ------------ 查询操作 ---------------- #
@app.route("/search_table", methods=["GET", "POST"])
def search_student():
    if request.method == "POST":
        get_search_con = request.form.get("search_op")
        print(get_search_con)
        # --------------------- 完成 ----------------------
        if get_search_con is not None:
            # 1 : 找到表格中的所有的字段
            get_name_list = get_collection_all_keys(py_collection)
            get_name_list.remove("_id")
            get_name_list.remove('age')
            print(get_name_list)

            res = es.search(index="test", size=20, body={
                "query": {
                    "multi_match": {
                        "query": str(get_search_con),
                        "fields": get_name_list
                    }
                }
            })
            answers = foreach(res)
        return render_template("search_answer.html", answers=answers)

        # # ----------  进行模糊查询 ------------- #
        # if get_search_con is not None:
        #     # 1 : 找到表格中的所有的字段
        #     get_name_list = get_collection_all_keys(py_collection)
        #     # 2 : 存储所有模糊查询的条件
        #     save_fuzzy_search = []
        #     for get_name in get_name_list:
        #         get_filter = {get_name: {"$regex": get_search_con}}
        #         save_fuzzy_search.append(get_filter)
        #     # or条件连接：说明满足其中的一个条件即可
        #     answers = py_collection.find({"$or": save_fuzzy_search})


@app.route("/more_search")
def get_search_information():
    return render_template("senior_search.html")


@app.route("/senior", methods=["GET", 'POST'])
def search_students_2():
    vec = {}
    if request.method == "POST":
        name = request.form.get("username")
        if name != "":
            q_json_1 = {
                "match": {
                    "username": name
                }
            }
        else:
            q_json_1 = {}
        password = request.form.get("password")
        if password != "":
            vec["password"] = password
            q_json_2 = {
                "match": {
                    "password": password
                }
            }
        else:
            q_json_2 = {}
        school = request.form.get("school")
        if school != "":
            q_json_3 = {
                "match": {
                    "school": school
                }
            }
        else:
            q_json_3 = {}
        phone = request.form.get("phone")
        if phone != "":
            q_json_4 = {
                "match": {
                    "phone": phone
                }
            }
        else:
            q_json_4 = {}
        work = request.form.get("work")
        if work != "":
            q_json_5 = {
                "match": {
                    "work": work
                }
            }
        else:
            q_json_5 = {}
        age1 = request.form.get("age_begin")
        age1 = int(age1) if age1 != "" else 0
        age2 = request.form.get("age_end")
        age2 = int(age2) if age2 != "" else 120
        q_json_6 = {
            "range": {
                "age": {
                    "gte": age1,
                    "lte": age2
                }
            }
        }

        res = es.search(index="test", body={
            "query": {
                "bool": {
                    "must": [
                            q_json_1,
                            q_json_2,
                            q_json_3,
                            q_json_4,
                            q_json_5,
                            q_json_6
                    ]
                }
            }

        })
        ans = foreach(res)
        if ans is None:
            return "<h1>哎呀，一个都没有找到啊</h1>"
        # 获取表单的信息，存入到
        # save_fuzzy_search = []

        # name = request.form.get("username")
        # if name != "":
        #     print(name)
        #     res = es.search(index='test', size=20, body={
        #         "query": {
        #             "match": {
        #                 "username": name  # 等于"1"
        #             }
        #         },
        #         "highlight": {
        #             # "boundary_scanner_locale": "zh_CN",
        #             "fields": {
        #                 "username": {
        #                     "pre_tags": ['<font color = "red">'],
        #                     "post_tags": ['</font>']
        #                 }
        #             }
        #         }
        #     })
        #     print(res)
        #     ans = foreach(res)
            # get_filter = {"username": {"$regex": name}}
            # save_fuzzy_search.append(get_filter)

        # pwd = request.form.get("password")
        # if pwd != "":
        #     print(pwd)
        #     get_filter = {"password": {"$regex": pwd}}
        #     save_fuzzy_search.append(get_filter)
        #
        # school = request.form.get("school")
        # if school != "":
        #     print(school)
        #     get_filter = {"school": {"$regex": school}}
        #     save_fuzzy_search.append(get_filter)
        #
        # phone = request.form.get("phone")
        # if phone != "":
        #     print(phone)
        #     get_filter = {"phone": {"$regex": phone}}
        #     save_fuzzy_search.append(get_filter)
        #
        # work = request.form.get("work")
        # if work != "":
        #     print(work)
        #     get_filter = {"work": {"$regex": work}}
        #     save_fuzzy_search.append(get_filter)
        #
        # age1, age2 = request.form.get("age_begin"), request.form.get("age_end")
        # get_filter = {"age": {"$in": list(range(int(age1) if age1 else 0, int(age2) + 1 if age2 else 120))}}
        # save_fuzzy_search.append(get_filter)
        #
        # if save_fuzzy_search:
        #     answers = py_collection.find({"$and": save_fuzzy_search})
        # else:
        #     answers = py_collection.find({})

        return render_template("search_answer.html", answers=ans)

    return "<h1>hello world</h1>"


if __name__ == '__main__':
    app.run(debug=True)
