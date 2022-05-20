#!/usr/bin/env python
# coding=utf-8
from pymongo import MongoClient
import pytz
from datetime import datetime,timedelta
import os 
from pprint import pprint
import fire
import json
import re
import traceback

import jionlp as jio
from dateparser import parse
import uuid

"""
done>>@mongo connect
done>>@mongo insert todo with label
done>>@mongo search by label or desc or abbr or date
done>>@mongo count sql
@mongo delete todo
@mongo edit todo
@mongo set done or doing
@mongo auto renew DDL?
@mongo cli version pipline!!
"""

#https://www.geeksforgeeks.org/python-mongodb-query/
mongo_hint = """
equality                 : {'key' : 'value'}
less than                : {'key' : { "$lt"  : 'value'}}
greater than             : {'key' : { "$gt"  : 'value'}}
less than or equal to    : {'key' : { "$lte" : 'value'}}
greater than or equal to : {'key' : { "$gte" : 'value'}}
not equal to             : {'key' : { "$ne"  : 'value'}}
Logical AND              : {'key' : { "$and" : [{'key1' : 'value1'}, {'key2' : 'value2'}]}}
Logical OR               : {'key' : { "$or"  : [{'key1' : 'value1'}, {'key2' : 'value2'}]}}
in                       : {'key' : { "$in" : ['value1', 'value2']}}
Logical NOT              : {'key' : { "$not" : {'key1' : 'value1'}}}
REGEX                    : {'key' : { "$regex" : 'value'}}
"""

mongo_query_example = """
#select all
{} 
#select import level 3
{"imp":3} 
# select ddl after tomorrow
{ddl:{$gt: date_明天}} 
{ddl:{$gt: date_tomorrow}} 
# select uuid
{uuid:dda4fe30-d83c-11ec-8e9a-bd24c27052d3} 
{uuid:{$regex: "dda4.*"}} 
"""

mongo_key_hint = """
_id     mongo id
uuid   (str) unique id
status (str) done, doing, freeze, delete
label  (str) todo label
abbr   (str) todo abbr
desc   (str) todo desc
imp    (int) important level
ddl    (datetime) deadline
create (datetime) create time
"""

key_order = [
    "uuid",
    "status",
    "label",
    "abbr",
    "desc",
    "imp",
    "create",
    "ddl",
]

print("  _                _          _______        _       ")
print(" | |              | |        |__   __|      | |      ")
print(" | |__   __ _  ___| | _____ _ __| | ___   __| | ___  ")
print(" | '_ \ / _` |/ __| |/ / _ \ '__| |/ _ \ / _` |/ _ \ ")
print(" | | | | (_| | (__|   <  __/ |  | | (_) | (_| | (_) |")
print(" |_| |_|\__,_|\___|_|\_\___|_|  |_|\___/ \__,_|\___/ ")
print("                                                     ")
print("                                             by eloco")


mongo_url =os.environ.get('TODO_MONGODB_URI')   or 'mongodb://localhost:27017/'
timezone  =os.environ.get('MYTZ')               or os.environ.get('TZ') # TZ is system default timezone
tzinfo    =pytz.timezone(timezone) 
assert "mongodb" in mongo_url

def generate_uuid():
    return str(uuid.uuid1())

def beautify_list(result):
    for r in result:
        print()
        for key in key_order:
            if key == "uuid":
                print(f"uuid: {r['uuid']}")
            elif type(r[key]) == datetime:
                print(f"""\t{key}:\t{r[key].strftime("%Y-%m-%d %H:%M:%S")}""")
            else:
                print(f"""\t{key}:\t{r[key]}""")

def extract_date(date_string : str):
    # support Chinese and English Natural Language (Chinese better due to the jionlp library)
    try:
        res = jio.parse_time(date_string, time_base=datetime.now(tzinfo),time_type='time_point')
        res = res["time"][-1]
        ddl_time = parse(res, settings={'TIMEZONE': timezone})
    except:
        ddl_time = parse(date_string, settings={'TIMEZONE': timezone})
    return ddl_time

def replace_jsonQuery(jsonQuery):
    if isinstance(jsonQuery,str):
        jsonQuery = jsonQuery.strip()
        if "date_" == jsonQuery[:5]:
            jsonQuery = extract_date(jsonQuery[5:])
        elif "num_"  == jsonQuery[:5]:
            jsonQuery = jsonQuery[5:]
    return(jsonQuery)

def walk_replace_jsonQuery(jsonQuery):
    if isinstance(jsonQuery,dict): 
        for key in jsonQuery:
            jsonQuery[key] = walk_replace_jsonQuery(jsonQuery[key])
    elif isinstance(jsonQuery,list):
        for ind,j in enumerate(jsonQuery):
            jsonQuery[ind]=walk_replace_jsonQuery(j)
    elif isinstance(jsonQuery,str):
        return(replace_jsonQuery(jsonQuery))
    return(jsonQuery)

class MongoTodo:

    default_ddl  = {
        "0": {"day":30*6 , "desc":"6 month" } ,
        "1": {"day":30*3 , "desc":"3 month" } ,
        "2": {"day":30*1 , "desc":"1 month" } ,
        "3": {"day":7*2  , "desc":"2 weeks" } ,
        "4": {"day":7*1  , "desc":"1 week"  } ,
        "5": {"day":3    , "desc":"3 day"   } ,
        "6": {"day":1    , "desc":"1 day"   } ,
    }

    def __init__(self):
        print("connecting to mongo...")
        self.client = MongoClient(
            host=mongo_url,
            tzinfo=tzinfo,
            tz_aware=True,
        )
        print("connected to mongo")
        self.db   = self.client["hacktodo"]
        self.col  = self.db["hacktodo"]

    def insert(self                                ,
               status : str ="todo"                ,
               label  : str ="test"                ,
               abbr   : str ="abbr of todo"        ,
               desc   : str ="description of todo" ,
               imp    : int =3                     ,
               ddl    : str =""                    ,
               uuid   : str =generate_uuid()       ,
              ):
        assert status in ["todo", "done", "closed", "freeze"]
        assert imp    in [0, 1, 2, 3, 4, 5]  # important level from 0 to 5 

        create_time  = datetime.now(tzinfo)

        # DDL generate 
        if ddl.strip() == "":
            # if ddl is empty, use default ddl
            ddl_time = create_time + timedelta(days=self.default_ddl[str(imp)]["day"])
        else:
            # if ddl is not empty, use user input ddl from nature language
            ddl_time = extract_date(ddl)
        assert isinstance(ddl_time, datetime)

        query_dict = {
            "status" : status,
            "label"  : label,
            "abbr"   : abbr,
            "desc"   : desc,
            "imp"    : imp,
            "ddl"    : ddl_time,
            "create" : create_time,
            "uuid"   : uuid,
        }

        check_query = {}
        for key in ["abbr","desc"]:
            check_query[key] = query_dict[key]

        find = list(self.col.find(check_query))
        if len(find) == 0:
            _insert = self.col.insert_one(query_dict)
            print(f"{query_dict['abbr']} just inserted, uuid: {uuid}")
            return uuid
        else:
            print(f"{query_dict['abbr']} already exists, {len(find)} records found")
            for f in list(self.col.find(check_query)):
                print(f"""uuid: {f["uuid"]} \t abbr: {f['abbr']}""")
            return find

    def simple_query(self                ,
                     method : str ="="   ,
                     key    : str =""    ,
                     value  : str =""    ,
                     beauty : bool =True ,
                     nums   : int  = 0   ,
                    ):
        assert_method = {
            "="     : "$eq",
            ">"     : "$gt",
            ">="    : "$gte",
            "<"     : "$lt",
            "<="    : "$lte",
            "!="    : "$ne",
            "regex" : "$regex",
        }
        try:
            assert method in assert_method.keys()
        except:
            print("method error")
            pprint(assert_method.keys())
            return
        assert key.strip() != "_id" , "key can not be _id"
        query_sql = {key : {assert_method[method] : value}}
        result    = list(self.col.find(query_sql))
        if nums   > 0:result = result[:nums]
        if beauty:beautify_list(result)
        else:return (result,len(result))

    def query(self,
            beauty : bool =True ,
            nums   : int  = 0   ,
            ):
        print("mongo_hint:")
        print(mongo_hint)
        print("key:")
        pprint(key_order)
        print()
        print("example:")
        print(mongo_query_example)
        while True:
            try:
                jsonStr     = input("query string: ")
                #jsonStr     = jsonStr.replace("$",'DolloR')
                jsonStr     = re.sub("((?=\D)[\w\$\-\+]+)\s*:", r'"\1":',  jsonStr)
                query_string= re.sub(":\s*((?=\D)[\w\$\-\+]+)", r':"\1"',  jsonStr)
                #query_string= query_string.replace('DolloR',"$")
                query_sql   = json.loads(query_string)
                query_sql   = walk_replace_jsonQuery(query_sql)
                for q in query_sql.keys():
                    if q == "_id":
                        raise Exception("_id is not allowed")
                print(f"\nfinal_query_sql: {query_sql}\n")
                break
            except Exception as e:
                traceback.print_exc()
                print(f"error: {e}")

        result    = list(self.col.find(query_sql))
        if nums   > 0:result = result[:nums]
        if beauty:beautify_list(result)
        else:return (result,len(result))
if __name__ == '__main__':
  fire.Fire(MongoTodo)
