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
import datetime
from google.appengine.api import channel
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

def sanitize(key):
  return re.sub('[^a-zA-Z0-9\-]', '-', key)

def make_client_id(room, user):
  return room.key().id_or_name() + '/' + user

def is_chrome_for_android(user_agent):
  return 'Android' in user_agent and 'Chrome' in user_agent

def get_default_stun_server(user_agent):
  # others you can try: stun.services.mozilla.com, stunserver.org
  return 'stun.l.google.com:19302'

# HD is on by default for desktop Chrome, but not Android or Firefox (yet)
def get_hd_default(user_agent):
  if 'Android' in user_agent or not 'Chrome' in user_agent:
    return 'false'
  return 'true'

def make_pc_config(stun_server, turn_server, ts_pwd, ice_transports):
  config = {}
  servers = []
  if stun_server:
    stun_config = 'stun:{}'.format(stun_server)
    servers.append({'urls':stun_config})
  if turn_server:
    turn_config = 'turn:{}'.format(turn_server)
    servers.append({'urls':turn_config, 'credential':ts_pwd})
  config['iceServers'] = servers
  if ice_transports:
    config['iceTransports'] = ice_transports
  return config

def create_channel(room, user, duration_minutes):
  client_id = make_client_id(room, user)
  return channel.create_channel(client_id, duration_minutes)

def make_loopback_answer(message):
  message = message.replace("\"offer\"", "\"answer\"")
  message = message.replace("a=ice-options:google-ice\\r\\n", "")
  return message

def handle_message(room, user, message):
  message_obj = json.loads(message)
  other_user = room.get_other_user(user)
  room_key = room.key().id_or_name()
  if message_obj['type'] == 'bye':
    # This would remove the other_user in loopback test too.
    # So check its availability before forwarding Bye message.
    room.remove_user(user)
    logging.info('User ' + user + ' quit from room ' + room_key)
    logging.info('Room ' + room_key + ' has state ' + str(room))
  if other_user and room.has_user(other_user):
    if message_obj['type'] == 'offer':
      # Special case the loopback scenario.
      if other_user == user:
        message = make_loopback_answer(message)
    on_message(room, other_user, message)
  else:
    # For unittest
    on_message(room, user, message)

def get_saved_messages(client_id):
  return Message.gql("WHERE client_id = :id", id=client_id)

def delete_saved_messages(client_id):
  messages = get_saved_messages(client_id)
  for message in messages:
    message.delete()
    logging.info('Deleted the saved message for ' + client_id)

def send_saved_messages(client_id):
  messages = get_saved_messages(client_id)
  for message in messages:
    channel.send_message(client_id, message.msg)
    logging.info('Delivered saved message to ' + client_id)
    message.delete()

def on_message(room, user, message):
  client_id = make_client_id(room, user)
  if room.is_connected(user):
    channel.send_message(client_id, message)
    logging.info('Delivered message to user ' + user)
  else:
    new_message = Message(client_id = client_id, msg = message)
    new_message.put()
    logging.info('Saved message for user ' + user)

def add_media_track_constraint(track_constraints, constraint_string):
  tokens = constraint_string.split(':')
  mandatory = True
  if len(tokens) == 2:
    # If specified, e.g. mandatory:minHeight=720, set mandatory appropriately.
    mandatory = (tokens[0] == 'mandatory')
  else:
    # Otherwise, default to mandatory, except for goog constraints, which
    # won't work in other browsers.
    mandatory = not tokens[0].startswith('goog')

  tokens = tokens[-1].split('=')
  if len(tokens) == 2:
    if mandatory:
      track_constraints['mandatory'][tokens[0]] = tokens[1]
    else:
      track_constraints['optional'].append({tokens[0]: tokens[1]})
  else:
    logging.error('Ignoring malformed constraint: ' + constraint_string)

def make_media_track_constraints(constraints_string):
  if not constraints_string or constraints_string.lower() == 'true':
    track_constraints = True
  elif constraints_string.lower() == 'false':
    track_constraints = False
  else:
    track_constraints = {'mandatory': {}, 'optional': []}
    for constraint_string in constraints_string.split(','):
      add_media_track_constraint(track_constraints, constraint_string)

  return track_constraints

def make_media_stream_constraints(audio, video, firefox_fake_device):
  stream_constraints = (
      {'audio': make_media_track_constraints(audio),
       'video': make_media_track_constraints(video)})
  if firefox_fake_device:
    stream_constraints['fake'] = True
  logging.info('Applying media constraints: ' + str(stream_constraints))
  return stream_constraints

def maybe_add_constraint(constraints, param, constraint):
  if (param.lower() == 'true'):
    constraints['optional'].append({constraint: True})
  elif (param.lower() == 'false'):
    constraints['optional'].append({constraint: False})

  return constraints

def make_pc_constraints(dtls, dscp, ipv6):
  constraints = { 'optional': [] }
  # Force on the new BWE in Chrome 35 and later.
  # TODO(juberti): Remove once Chrome 36 is stable.
  constraints['optional'].append({'googImprovedWifiBwe': True})
  maybe_add_constraint(constraints, dtls, 'DtlsSrtpKeyAgreement')
  maybe_add_constraint(constraints, dscp, 'googDscp')
  maybe_add_constraint(constraints, ipv6, 'googIPv6')

  return constraints

def make_offer_constraints():
  constraints = { 'mandatory': {}, 'optional': [] }
  return constraints

def append_url_arguments(request, link):
  for argument in request.arguments():
    if argument != 'r':
      link += ('&' + cgi.escape(argument, True) + '=' +
                cgi.escape(request.get(argument), True))
  return link

def write_response(response, response_type, target_page, params):
  if response_type == 'json':
    content = json.dumps(params)
  else:
    template = jinja_environment.get_template(target_page)
    content = template.render(params)
  response.out.write(content)

# This database is to store the messages from the sender client when the
# receiver client is not ready to receive the messages.
# Use TextProperty instead of StringProperty for msg because
# the session description can be more than 500 characters.
class Message(db.Model):
  client_id = db.StringProperty()
  msg = db.TextProperty()

class Room(db.Model):
  """All the data we store for a room"""
  user1 = db.StringProperty()
  user2 = db.StringProperty()
  user1_connected = db.BooleanProperty(default=False)
  user2_connected = db.BooleanProperty(default=False)

  def __str__(self):
    result = '['
    if self.user1:
      result += "%s-%r" % (self.user1, self.user1_connected)
    if self.user2:
      result += ", %s-%r" % (self.user2, self.user2_connected)
    result += ']'
    return result

  def get_occupancy(self):
    occupancy = 0
    if self.user1:
      occupancy += 1
    if self.user2:
      occupancy += 1
    return occupancy

  def get_other_user(self, user):
    if user == self.user1:
      return self.user2
    elif user == self.user2:
      return self.user1
    else:
      return None

  def has_user(self, user):
    return (user and (user == self.user1 or user == self.user2))

  def add_user(self, user):
    if not self.user1:
      self.user1 = user
    elif not self.user2:
      self.user2 = user
    else:
      raise RuntimeError('room is full')
    self.put()

  def remove_user(self, user):
    delete_saved_messages(make_client_id(self, user))
    if user == self.user2:
      self.user2 = None
      self.user2_connected = False
    if user == self.user1:
      if self.user2:
        self.user1 = self.user2
        self.user1_connected = self.user2_connected
        self.user2 = None
        self.user2_connected = False
      else:
        self.user1 = None
        self.user1_connected = False
    if self.get_occupancy() > 0:
      self.put()
    else:
      self.delete()

  def set_connected(self, user):
    if user == self.user1:
      self.user1_connected = True
    if user == self.user2:
      self.user2_connected = True
    self.put()

  def is_connected(self, user):
    if user == self.user1:
      return self.user1_connected
    if user == self.user2:
      return self.user2_connected


# kendi yazdığımız modeller

class chatRoom(db.Model):
  """All the data we store for a room"""
  user_1 = db.StringProperty()
  user_2 = db.StringProperty()
  room_key = db.StringProperty()
  user_1_time = db.DateTimeProperty()
  user_2_time = db.DateTimeProperty()



@db.transactional
def connect_user_to_room(room_key, user):
  room = Room.get_by_key_name(room_key)
  # Check if room has user in case that disconnect message comes before
  # connect message with unknown reason, observed with local AppEngine SDK.
  if room and room.has_user(user):
    room.set_connected(user)
    logging.info('User ' + user + ' connected to room ' + room_key)
    logging.info('Room ' + room_key + ' has state ' + str(room))
  else:
    logging.warning('Unexpected Connect Message to room ' + room_key)
  return room

class ConnectPage(webapp2.RequestHandler):
  def post(self):
    key = self.request.get('from')
    room_key, user = key.split('/')
    with LOCK:
      room = connect_user_to_room(room_key, user)
      if room and room.has_user(user):
        send_saved_messages(make_client_id(room, user))

class DisconnectPage(webapp2.RequestHandler):
  def post(self):
    key = self.request.get('from')
    room_key, user = key.split('/')
    with LOCK:
      room = Room.get_by_key_name(room_key)
      if room and room.has_user(user):
        other_user = room.get_other_user(user)
        room.remove_user(user)
        logging.info('User ' + user + ' removed from room ' + room_key)
        logging.info('Room ' + room_key + ' has state ' + str(room))
        if other_user and other_user != user:
          channel.send_message(make_client_id(room, other_user),
                               '{"type":"bye"}')
          logging.info('Sent BYE to ' + other_user)
    logging.warning('User ' + user + ' disconnected from room ' + room_key)


class MessagePage(webapp2.RequestHandler):
  def post(self):
    message = self.request.body
    room_key = self.request.get('r')
    user = self.request.get('u')
    with LOCK:
      room = Room.get_by_key_name(room_key)
      if room:
        handle_message(room, user, message)
      else:
        logging.warning('Unknown room ' + room_key)

class MainPage(webapp2.RequestHandler):
  """The main UI page, renders the 'index.html' template."""
  def get(self):
    """Renders the main page. When this page is shown, we create a new
    channel to push asynchronous updates to the client."""

    # Append strings to this list to have them thrown up in message boxes. This
    # will also cause the app to fail.
    error_messages = []
    # Get the base url without arguments.
    base_url = self.request.path_url
    user_agent = self.request.headers['User-Agent']
    room_key = sanitize(self.request.get('r'))
    response_type = self.request.get('t')
    stun_server = self.request.get('ss')
    if not stun_server:
      stun_server = get_default_stun_server(user_agent)
    turn_server = self.request.get('ts')
    ts_pwd = self.request.get('tp')
    ice_transports = self.request.get('it')

    # Use "audio" and "video" to set the media stream constraints. Defined here:
    # http://goo.gl/V7cZg
    #
    # "true" and "false" are recognized and interpreted as bools, for example:
    #   "?audio=true&video=false" (Start an audio-only call.)
    #   "?audio=false" (Start a video-only call.)
    # If unspecified, the stream constraint defaults to True.
    #
    # To specify media track constraints, pass in a comma-separated list of
    # key/value pairs, separated by a "=". Examples:
    #   "?audio=googEchoCancellation=false,googAutoGainControl=true"
    #   (Disable echo cancellation and enable gain control.)
    #
    #   "?video=minWidth=1280,minHeight=720,googNoiseReduction=true"
    #   (Set the minimum resolution to 1280x720 and enable noise reduction.)
    #
    # Keys starting with "goog" will be added to the "optional" key; all others
    # will be added to the "mandatory" key.
    # To override this default behavior, add a "mandatory" or "optional" prefix
    # to each key, e.g.
    #   "?video=optional:minWidth=1280,optional:minHeight=720,
    #           mandatory:googNoiseReduction=true"
    #   (Try to do 1280x720, but be willing to live with less; enable
    #    noise reduction or die trying.)
    #
    # The audio keys are defined here: talk/app/webrtc/localaudiosource.cc
    # The video keys are defined here: talk/app/webrtc/videosource.cc
    audio = self.request.get('audio')
    video = self.request.get('video')

    # Pass firefox_fake_device=1 to pass fake: true in the media constraints,
    # which will make Firefox use its built-in fake device.
    firefox_fake_device = self.request.get('firefox_fake_device')

    # The hd parameter is a shorthand to determine whether to open the
    # camera at 720p. If no value is provided, use a platform-specific default.
    # When defaulting to HD, use optional constraints, in case the camera
    # doesn't actually support HD modes.
    hd = self.request.get('hd').lower()
    if hd and video:
      message = 'The "hd" parameter has overridden video=' + video
      logging.error(message)
      error_messages.append(message)
    if hd == 'true':
      video = 'mandatory:minWidth=1280,mandatory:minHeight=720'
    elif not hd and not video and get_hd_default(user_agent) == 'true':
      video = 'optional:minWidth=1280,optional:minHeight=720'

    if self.request.get('minre') or self.request.get('maxre'):
      message = ('The "minre" and "maxre" parameters are no longer supported. '
                 'Use "video" instead.')
      logging.error(message)
      error_messages.append(message)

    # Allow preferred audio and video codecs to be overridden.
    audio_send_codec = self.request.get('asc', default_value = '')
    audio_receive_codec = self.request.get('arc', default_value = '')
    video_send_codec = self.request.get('vsc', default_value = '')
    video_receive_codec = self.request.get('vrc', default_value = '')

    # Read url param controlling whether we send stereo.
    stereo = self.request.get('stereo', default_value = 'false')

    # Read url param controlling whether we send Opus FEC.
    opusfec = self.request.get('opusfec', default_value = 'true')

    # Read url param for Opus max sample rate.
    opusmaxpbr = self.request.get('opusmaxpbr', default_value = '')

    # Read url params audio send bitrate (asbr) & audio receive bitrate (arbr).
    asbr = self.request.get('asbr', default_value = '')
    arbr = self.request.get('arbr', default_value = '')

    # Read url params video send bitrate (vsbr) & video receive bitrate (vrbr).
    vsbr = self.request.get('vsbr', default_value = '')
    vrbr = self.request.get('vrbr', default_value = '')

    # Read url params for the initial video send bitrate (vsibr).
    vsibr = self.request.get('vsibr', default_value = '')

    # Options for controlling various networking features.
    dtls = self.request.get('dtls')
    dscp = self.request.get('dscp')
    ipv6 = self.request.get('ipv6')

    # Stereoscopic rendering.  Expects remote video to be a side-by-side view of
    # two cameras' captures, which will each be fed to one eye.
    ssr = self.request.get('ssr')
    # Avoid pulling down vr.js (>25KB, minified) if not needed.
    include_vr_js = ''
    if ssr == 'true':
      include_vr_js = ('<script src="/js/vr.js"></script>\n' +
                       '<script src="/js/stereoscopic.js"></script>')

    # Disable pinch-zoom scaling since we manage video real-estate explicitly
    # (via full-screen) and don't want devicePixelRatios changing dynamically.
    meta_viewport = ''
    if is_chrome_for_android(user_agent):
      meta_viewport = ('<meta name="viewport" content="width=device-width, ' +
                       'user-scalable=no, initial-scale=1, maximum-scale=1">')

    debug = self.request.get('debug')
    if debug == 'loopback':
      # Set dtls to false as DTLS does not work for loopback.
      dtls = 'false'

    # token_timeout for channel creation, default 30min, max 1 days, min 3min.
    token_timeout = self.request.get_range('tt',
                                           min_value = 3,
                                           max_value = 1440,
                                           default = 30)

    unittest = self.request.get('unittest')
    if unittest:
      # Always create a new room for the unit tests.
      room_key = generate_random(8)

    if not room_key:
      redirect = str('https://shufflechat.me/getRoomHtml')
      self.redirect(redirect)
      logging.info('Redirecting visitor to base URL to ' + redirect)
      return

    logging.info('Preparing to add user to room ' + room_key)
    user = None
    initiator = 0
    with LOCK:
      room = Room.get_by_key_name(room_key)
      if not room and debug != "full":
        # New room.
        user = generate_random(8)
        room = Room(key_name = room_key)
        room.add_user(user)
        if debug != 'loopback':
          initiator = 0
        else:
          room.add_user(user)
          initiator = 1
      elif room and room.get_occupancy() == 1 and debug != 'full':
        # 1 occupant.
        user = generate_random(8)
        room.add_user(user)
        initiator = 1
      else:

        redirect = str('https://shufflechat.me/getRoomHtml')
        self.redirect(redirect)
        # 2 occupants (full).

        #params = {
        #  'error': 'full',
        #  'error_messages': ['The room is full.'],
        #  'room_key': room_key
        #}
        #write_response(self.response, response_type, 'full.html', params)
        logging.info('Room ' + room_key + ' is full')
        return

    logging.info('User ' + user + ' added to room ' + room_key)
    logging.info('Room ' + room_key + ' has state ' + str(room))

    if turn_server == 'false':
      turn_server = None
      turn_url = ''
    else:
      turn_url = 'https://computeengineondemand.appspot.com/'
      turn_url = turn_url + 'turn?' + 'username=' + user + '&key=4080218913'

    room_link = base_url + '?r=' + room_key
    room_link = append_url_arguments(self.request, room_link)
    token = create_channel(room, user, token_timeout)
    pc_config = make_pc_config(stun_server, turn_server, ts_pwd, ice_transports)
    pc_constraints = make_pc_constraints(dtls, dscp, ipv6)
    offer_constraints = make_offer_constraints()
    media_constraints = make_media_stream_constraints(audio, video,
                                                      firefox_fake_device)

    params = {
      'error_messages': error_messages,
      'token': token,
      'me': user,
      'room_key': room_key,
      'room_link': room_link,
      'initiator': initiator,
      'pc_config': json.dumps(pc_config),
      'pc_constraints': json.dumps(pc_constraints),
      'offer_constraints': json.dumps(offer_constraints),
      'media_constraints': json.dumps(media_constraints),
      'turn_url': turn_url,
      'stereo': stereo,
      'opusfec': opusfec,
      'opusmaxpbr': opusmaxpbr,
      'arbr': arbr,
      'asbr': asbr,
      'vrbr': vrbr,
      'vsbr': vsbr,
      'vsibr': vsibr,
      'audio_send_codec': audio_send_codec,
      'audio_receive_codec': audio_receive_codec,
      'video_send_codec': video_send_codec,
      'video_receive_codec': video_receive_codec,
      'ssr': ssr,
      'include_vr_js': include_vr_js,
      'meta_viewport': meta_viewport
    }

    if unittest:
      target_page = 'test/test_' + unittest + '.html'
    else:
      target_page = 'index.html'
    write_response(self.response, response_type, target_page, params)




class getRoomHtml(webapp2.RequestHandler):
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

      redirect = str('https://shufflechat.me/?r=' + create_room)
      self.redirect(redirect)
      logging.info('Oda olusturuldu => '+ create_room+" - " + create_user)
      return
    else:

      acc = q.get()
      key = acc.key()

      obj = db.get(key)
      obj.delete()

      room_key = wait_users[0].room_key

      redirect = str('https://shufflechat.me/?r=' + room_key)
      self.redirect(redirect)
      logging.info('kullanici odaya atilti => '+ room_key+" - " + create_user)
      return

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/getRoomHtml', getRoomHtml),
    ('/message', MessagePage),
    ('/_ah/channel/connected/', ConnectPage),
    ('/_ah/channel/disconnected/', DisconnectPage)
  ], debug=True)
