/*
 *  Copyright (c) 2014 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree.
 */

'use strict';

var video1 = document.querySelector('video#video1');
var video2 = document.querySelector('video#video2');

var startButton = document.querySelector('button#startButton');
var callButton = document.querySelector('button#callButton');
var hangupButton = document.querySelector('button#hangupButton');
startButton.disabled = false;
callButton.disabled = true;
hangupButton.disabled = true;
startButton.onclick = start;
callButton.onclick = call;
hangupButton.onclick = hangup;

var pc1StateDiv = document.querySelector('div#pc1State');
var pc1IceStateDiv = document.querySelector('div#pc1IceState');
var pc2StateDiv = document.querySelector('div#pc2State');
var pc2IceStateDiv = document.querySelector('div#pc2IceState');

var localstream, pc1, pc2;

var sdpConstraints = {
  mandatory: {
    OfferToReceiveAudio: true,
    OfferToReceiveVideo: true
  }
};

function gotStream(stream) {
  trace('Received local stream');
  // Call the polyfill wrapper to attach the media stream to this element.
  attachMediaStream(video1, stream);
  localstream = stream;
  callButton.disabled = false;
}

function start() {
  trace('Requesting local stream');
  startButton.disabled = true;
  // Call into getUserMedia via the polyfill (adapter.js).
  getUserMedia({
      audio: true,
      video: true
    }, gotStream,
    function(e) {
      alert('getUserMedia() error: ', e.name);
    });
}

function call() {
  callButton.disabled = true;
  hangupButton.disabled = false;
  trace('Starting call');
  var videoTracks = localstream.getVideoTracks();
  var audioTracks = localstream.getAudioTracks();
  if (videoTracks.length > 0) {
    trace('Using Video device: ' + videoTracks[0].label);
  }
  if (audioTracks.length > 0) {
    trace('Using Audio device: ' + audioTracks[0].label);
  }
  var servers = null;
  var pcConstraints = {
    'optional': []
  };

  pc1 = new RTCPeerConnection(servers, pcConstraints);
  trace('Created local peer connection object pc1');
  pc1StateDiv.textContent = pc1.signalingState || pc1.readyState;
  if (typeof pc1.onsignalingstatechange !== 'undefined') {
    pc1.onsignalingstatechange = stateCallback1;
  } else {
    pc1.onstatechange = stateCallback1;
  }
  pc1IceStateDiv.textContent = pc1.iceConnectionState;
  if (pc1.oniceconnectionstatechange) {
    pc1.oniceconnectionstatechange = iceStateCallback1;
  } else {
    pc1.onicechange = iceStateCallback1;
  }
  pc1.onicecandidate = iceCallback1;

  pc2 = new RTCPeerConnection(servers, pcConstraints);
  trace('Created remote peer connection object pc2');
  pc2StateDiv.textContent = pc2.signalingState || pc2.readyState;
  if (pc2.onsignalingstatechange) {
    pc2.onsignalingstatechange = stateCallback2;
  } else {
    pc2.onstatechange = stateCallback2;
  }
  pc2IceStateDiv.textContent = pc2.iceConnectionState;
  if (typeof pc2.oniceconnectionstatechange !== 'undefined') {
    pc2.oniceconnectionstatechange = iceStateCallback2;
  } else {
    pc2.onicechange = iceStateCallback2;
  }
  pc2.onicecandidate = iceCallback2;
  pc2.onaddstream = gotRemoteStream;
  pc1.addStream(localstream);
  trace('Adding Local Stream to peer connection');
  pc1.createOffer(gotDescription1, onCreateSessionDescriptionError);
}

function onCreateSessionDescriptionError(error) {
  trace('Failed to create session description: ' + error.toString());
}

function gotDescription1(description) {
  pc1.setLocalDescription(description);
  trace('Offer from pc1: \n' + description.sdp);
  pc2.setRemoteDescription(description);
  pc2.createAnswer(gotDescription2, onCreateSessionDescriptionError,
    sdpConstraints);
}

function gotDescription2(description) {
  pc2.setLocalDescription(description);
  trace('Answer from pc2 \n' + description.sdp);
  pc1.setRemoteDescription(description);
}

function hangup() {
  trace('Ending call');
  pc1.close();
  pc2.close();
  pc1StateDiv.textContent += ' => ' + pc1.signalingState || pc1.readyState;
  pc2StateDiv.textContent += ' => ' + pc2.signalingState || pc2.readyState;
  pc1IceStateDiv.textContent += ' => ' + pc1.iceConnectionState;
  pc2IceStateDiv.textContent += ' => ' + pc2.iceConnectionState;
  pc1 = null;
  pc2 = null;
  hangupButton.disabled = true;
  callButton.disabled = false;
}

function gotRemoteStream(e) {
  attachMediaStream(video2, e.stream);
  trace('Got remote stream');
}

function stateCallback1() {
  var state;
  if (pc1) {
    state = pc1.signalingState || pc1.readyState;
    trace('pc1 state change callback, state: ' + state);
    pc1StateDiv.textContent += ' => ' + state;
  }
}

function stateCallback2() {
  var state;
  if (pc2) {
    state = pc2.signalingState || pc2.readyState;
    trace('pc2 state change callback, state: ' + state);
    pc2StateDiv.textContent += ' => ' + state;
  }
}

function iceStateCallback1() {
  var iceState;
  if (pc1) {
    iceState = pc1.iceConnectionState;
    trace('pc1 ICE connection state change callback, state: ' + iceState);
    pc1IceStateDiv.textContent += ' => ' + iceState;
  }
}

function iceStateCallback2() {
  var iceState;
  if (pc2) {
    iceState = pc2.iceConnectionState;
    trace('pc2 ICE connection state change callback, state: ' + iceState);
    pc2IceStateDiv.textContent += ' => ' + iceState;
  }
}

function iceCallback1(event) {
  if (event.candidate) {
    pc2.addIceCandidate(new RTCIceCandidate(event.candidate),
      onAddIceCandidateSuccess, onAddIceCandidateError);
    trace('Local ICE candidate: \n' + event.candidate.candidate);
  } else {
    trace('End of candidates added to PC2');
  }
}

function iceCallback2(event) {
  if (event.candidate) {
    pc1.addIceCandidate(new RTCIceCandidate(event.candidate),
      onAddIceCandidateSuccess, onAddIceCandidateError);
    trace('Remote ICE candidate: \n ' + event.candidate.candidate);
  } else {
    trace('End of candidates added to PC1');
  }
}

function onAddIceCandidateSuccess() {
  trace('AddIceCandidate success.');
}

function onAddIceCandidateError(error) {
  trace('Failed to add Ice Candidate: ' + error.toString());
}
