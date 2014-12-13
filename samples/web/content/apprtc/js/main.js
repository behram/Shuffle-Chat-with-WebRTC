/*
 *  Copyright (c) 2014 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree.
 */

/* More information about these options at jshint.com/docs/options */

// Variables defined in and used from apprtc/index.html.
/* globals params, setupStereoscopic */
/* exported doGetUserMedia, enterFullScreen, initialize, onHangup */

// Variables defined in and used from util.js.
/* globals doGetUserMedia, maybeRequestTurn */
/* exported xmlhttp, onUserMediaSuccess, onUserMediaError */

// Variables defined in and used from infobox.js.
/* globals showInfoDiv, toggleInfoDiv, updateInfoDiv */
/* exported getStatsTimer, infoDiv */

// Variables defined in and used from stats.js.
/* exported prevStats, stats */

// Variables defined in and used from signaling.js.
/* globals openChannel, maybeStart, sendMessage */
/* exported channelReady, gatheredIceCandidateTypes, sdpConstraints, turnDone,
   onRemoteHangup, waitForRemoteVideo */

'use strict';

var infoDiv = document.querySelector('#info');
var localVideo = document.querySelector('#local-video');
var miniVideo = document.querySelector('#mini-video');
var remoteCanvas = document.querySelector('#remote-canvas');
var remoteVideo = document.querySelector('#remote-video');
var sharingDiv = document.querySelector('#sharing');
var statusDiv = document.querySelector('#status');
var videosDiv = document.querySelector('#videos');

var channelReady = false;
// Types of gathered ICE Candidates.
var gatheredIceCandidateTypes = {
  Local: {},
  Remote: {}
};
var getStatsTimer;
var hasLocalStream;
var errorMessages = [];
var isAudioMuted = false;
var isVideoMuted = false;
var localStream;
var msgQueue = [];
var pc = null;
var remoteStream;
// Set up audio and video regardless of what devices are present.
// Disable comfort noise for maximum audio quality.
var sdpConstraints = {
  'mandatory': {
    'OfferToReceiveAudio': true,
    'OfferToReceiveVideo': true
  },
  'optional': [{
    'VoiceActivityDetection': false
  }]
};

var signalingReady = false;
var socket;
var started = false;
var startTime;
var endTime;
var stats;
var prevStats;
var turnDone = false;
var xmlhttp;

function initialize() {
  var roomErrors = params.errorMessages;
  if (roomErrors.length > 0) {
    console.log(roomErrors);
    for (var i = 0; i < roomErrors.length; ++i) {
      window.alert(roomErrors[i]);
    }
    return;
  }

  document.body.ondblclick = toggleFullScreen;

  trace('Initializing; room=' + params.roomId + '.');

  // NOTE: AppRTCClient.java searches & parses this line; update there when
  // changing here.
  openChannel();
  maybeRequestTurn();

  // Caller is always ready to create peerConnection.
  signalingReady = params.isInitiator;

  if (params.mediaConstraints.audio === false &&
      params.mediaConstraints.video === false) {
    hasLocalStream = false;
    maybeStart();
  } else {
    hasLocalStream = true;
    doGetUserMedia();
  }
}


function onUserMediaSuccess(stream) {
  trace('User has granted access to local media.');
  $("#shuffleButton").html("Connecting..");
  // Call the polyfill wrapper to attach the media stream to this element.
  attachMediaStream(localVideo, stream);
  localStream = stream;
  // Caller creates PeerConnection.
  maybeStart();
  displayStatus('');
  if (params.isInitiator === 0) {
    displaySharingInfo();
  }
  localVideo.classList.add('active');
}

function onUserMediaError(error) {
  var errorMessage = 'Failed to get access to local media. Error name was ' +
      error.name + '. Continuing without sending a stream.';
  displayError(errorMessage);
  alert(errorMessage);

  hasLocalStream = false;
  maybeStart();
}

function hangup() {
  trace('Hanging up.');
  displayStatus('Hanging up');
  transitionToDone();
  localStream.stop();
  stop();
  // will trigger BYE from server
  socket.close();
}

function onRemoteHangup() {
  $("#shuffleButton").html("Shuffle Room");
  displayStatus('The remote side hung up.');
  params.isInitiator = 0;
  transitionToWaiting();
  stop();
}

function stop() {
  started = false;
  signalingReady = false;
  isAudioMuted = false;
  isVideoMuted = false;
  pc.close();
  pc = null;
  remoteStream = null;
  msgQueue.length = 0;
}

function waitForRemoteVideo() {
  // Wait for the actual video to start arriving before moving to the active
  // call state.
  if (remoteVideo.readyState >= 2) {  // i.e. can play
    trace('Remote video started; currentTime: ' + remoteVideo.currentTime);

    transitionToActive();
  } else {
    remoteVideo.oncanplay = waitForRemoteVideo;
  }
}

function transitionToActive() {
  $("#shuffleButton").html("Shuffle");
  // Stop waiting for remote video.
  remoteVideo.oncanplay = undefined;
  endTime = window.performance.now();
  trace('Call setup time: ' + (endTime - startTime).toFixed(0) + 'ms.');
  updateInfoDiv();

  // Prepare the remote video and PIP elements.
  if (params.isStereoscopic) {
    miniVideo.classList.remove('active');
    miniVideo.classList.add('hidden');
    setupStereoscopic(remoteVideo, remoteCanvas);
  } else {
    reattachMediaStream(miniVideo, localVideo);
  }

  // Transition opacity from 0 to 1 for the remote and mini videos.
  remoteVideo.classList.add('active');
  miniVideo.classList.add('active');
  // Transition opacity from 1 to 0 for the local video.
  localVideo.classList.remove('active');
  localVideo.src = '';
  // Rotate the div containing the videos 180 deg with a CSS transform.
  videosDiv.classList.add('active');
  displayStatus('');
}

function transitionToWaiting() {

   // Stop waiting for remote video.
  remoteVideo.oncanplay = undefined;
  startTime = null;
  // Rotate the div containing the videos -180 deg with a CSS transform.
  videosDiv.classList.remove('active');
  setTimeout(function() {
    localVideo.src = miniVideo.src;
    miniVideo.src = '';
    remoteVideo.src = '';
  }, 800);
  // Transition opacity from 0 to 1 for the local video.
  localVideo.classList.add('active');
  // Transition opacity from 1 to 0 for the remote and mini videos.
  remoteVideo.classList.remove('active');
  miniVideo.classList.remove('active');
}

function transitionToDone() {
   // Stop waiting for remote video.
  remoteVideo.oncanplay = undefined;
  localVideo.classList.remove('active');
  remoteVideo.classList.remove('active');
  miniVideo.classList.remove('active');
  displayStatus('You have left the call. <a href=\'' + params.roomLink +
      '\'>Click here</a> to rejoin.');
}

function toggleVideoMute() {
  var videoTracks = localStream.getVideoTracks();
  if (videoTracks.length === 0) {
    trace('No local video available.');
    return;
  }

  var newMuted = !isVideoMuted;
  trace('Toggling video mute state.');
  for (var i = 0; i < videoTracks.length; ++i) {
    videoTracks[i].enabled = !newMuted;
  }

  isVideoMuted = newMuted;
  trace('Video ' + isVideoMuted ? 'muted.' : 'unmuted.');
}

function toggleAudioMute() {
  var audioTracks = localStream.getAudioTracks();
  if (audioTracks.length === 0) {
    trace('No local audio available.');
    return;
  }

  var newMuted = !isAudioMuted;
  trace('Toggling audio mute state.');
  for (var i = 0; i < audioTracks.length; ++i) {
    audioTracks[i].enabled = !newMuted;
  }

  isAudioMuted = newMuted;
  trace('Audio ' + isVideoMuted ? 'muted.' : 'unmuted.');
}

// Spacebar, or m: toggle audio mute.
// c: toggle camera(video) mute.
// f: toggle fullscreen.
// i: toggle info panel.
// q: quit (hangup)
// Return false to screen out original Chrome shortcuts.
document.onkeypress = function(event) {
  switch (String.fromCharCode(event.charCode)) {
    case ' ':
    case 'm':
      toggleAudioMute();
      return false;
    case 'c':
      toggleVideoMute();
      return false;
    case 'f':
      toggleFullScreen();
      return false;
    case 'i':
      toggleInfoDiv();
      return false;
    case 'q':
      hangup();
      return false;
    default:
      return;
  }
};

// Send a BYE on refreshing or leaving a page
// to ensure the room is cleaned up for the next session.
window.onbeforeunload = function() {
  sendMessage({
    type: 'bye'
  });
};

function displaySharingInfo() {
  sharingDiv.classList.add('active');
}

function displayStatus(status) {
  if (status === '') {
    statusDiv.classList.remove('active');
  } else {
    statusDiv.classList.add('active');
  }
  statusDiv.innerHTML = status;
}

function displayError(error) {
  trace(error);
  errorMessages.push(error);
  updateInfoDiv();
  showInfoDiv();
}

function toggleFullScreen() {
  try {
    // TODO: add shim so not Chrome only
    if (document.webkitIsFullScreen) {
      document.webkitCancelFullScreen();
    } else {
      videosDiv.webkitRequestFullScreen();
      remoteCanvas.webkitRequestFullScreen();
    }
  } catch (event) {
    trace(event);
  }
}
