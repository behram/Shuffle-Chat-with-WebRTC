#!/usr/bin/python2.4
# -*- coding: utf-8 -*-
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""WebRTC Demo

This module demonstrates the WebRTC API by implementing a simple video chat app.
"""

import cgi
import logging
import os
import random
import re
import json
import jinja2
import webapp2
import threading
import time
import datetime
from google.appengine.api import channel
from google.appengine.api import memcache
from google.appengine.ext import db

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

# Lock for syncing DB operation in concurrent requests handling.
# TODO(brave): keeping working on improving performance with thread syncing.
# One possible method for near future is to reduce the message caching.
LOCK = threading.RLock()

def generate_random(length):
  word = ''
  for _ in range(length):
    word += random.choice('0123456789')
  return word

# kendi yazdığımız modeller

class chatRoom(db.Model):
  """All the data we store for a room"""
  user_1 = db.StringProperty()
  user_2 = db.StringProperty()
  room_key = db.StringProperty()
  user_1_time = db.DateTimeProperty()
  user_2_time = db.DateTimeProperty()


class getRoom(webapp2.RequestHandler):
  def get(self):

    # istek için bir user, room create
    create_user = generate_random(10)
    create_room = generate_random(8)

    q = chatRoom.all()
    q.filter("user_2", "NULL")
    q.order("-user_1_time")
    q.fetch(limit=1)
    wait_users = q.fetch(limit=1)
    wait_user_count = q.count()

    if wait_user_count == 0:
      put_wait_user = chatRoom()
      put_wait_user.user_1 = create_user
      put_wait_user.user_2 = "NULL"
      put_wait_user.room_key = create_room
      put_wait_user.user_1_time = datetime.datetime.now()

      put_wait_user.put()

      self.response.headers['Content-Type'] = 'application/json'
      self.response.write("{'room_key': '"+ create_room +"','user':'"+ create_user +"','room_guest_count':'0'}")
      logging.info('Oda oluşturuldu => '+ create_room+" - " + create_user)
      return
    else:

      acc = q.get()
      key = acc.key()

      obj = db.get(key)
      obj.delete()

      room_key = wait_users[0].room_key

      self.response.headers['Content-Type'] = 'application/json'
      self.response.write("{'room_key': '"+ room_key +"','user':'"+ create_user +"','room_guest_count':'1'}")
      return

app = webapp2.WSGIApplication([
    ('/getRoom', getRoom)
  ], debug=True)
