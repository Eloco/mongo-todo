#!/usr/bin/env python
# coding=utf-8
from pymongo import MongoClient
import pytz
from datetime import datetime
import os 
import emoji
import time
from pprint import pprint

import jionlp as jio
from dateparser import parse

"""
done>>@mongo connect
done>>@mongo insert todo with label
@mongo search by label or desc or abbr or date
@mongo delete todo
@mongo edit todo
@mongo set done or doing
@mongo auto renew DDL?
"""

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
              ):
        assert status in ["todo", "done", "closed", "freeze"]
        assert imp    in [0, 1, 2, 3, 4, 5]  # important level from 0 to 5 

        create_time  = datetime.now(tzinfo)

        # DDL generate
        if ddl.strip() == "":
            ddl = create_time + timedelta(days=self.default_ddl[imp]["day"])
        else:
            # support Chinese and English Natural Language (Chinese better due to the jionlp library)
            try:
                res = jio.parse_time(ddl, time_base=create_time,time_type='time_point')
                res = res["time"][-1]
                ddl_time = parse(res, settings={'TIMEZONE': timezone})
            except:
                ddl_time = parse(ddl, settings={'TIMEZONE': timezone})
        assert isinstance(ddl_time, datetime)

        query_dict = {
            "status" : status,
            "label"  : label,
            "abbr"   : abbr,
            "desc"   : desc,
            "imp"    : imp,
            "ddl"    : ddl_time,
            "create" : create_time,
        }


        check_query = {}
        for key in ["abbr","desc"]:
            check_query[key] = query_dict[key]
        if (find:= self.col.count_documents(check_query)) == 0:
            self.col.insert_one(query_dict)
            print(f"{query_dict['abbr']} just inserted")
        else:
            print(f"{query_dict['abbr']} already exists, {find} records found")

    def find_all(self):
        return list(self.col.find({}))

a = MongoTodo()
#a.insert(abbr="haha")
pprint(a.find_all())
