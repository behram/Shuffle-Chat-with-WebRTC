/*
 *  Copyright (c) 2014 The WebRTC project authors. All Rights Reserved.
 *
 *  Use of this source code is governed by a BSD-style license
 *  that can be found in the LICENSE file in the root of the source
 *  tree.
 */
'use strict';

addTest('Connectivity', 'Udp connectivity', testUdpConnectivity);
addTest('Connectivity', 'Tcp connectivity', testTcpConnectivity);
addTest('Connectivity', 'Ipv6 enabled', testHasIpv6Candidates);

// Test whether it can connect via UDP to a TURN server
// Get a TURN config, and try to get a relay candidate using UDP.
function testUdpConnectivity() {
  Call.asyncCreateTurnConfig(
      function(config) { 
        filterConfig(config, 'udp');
        gatherCandidates(config, null, Call.isRelay);
      },
      reportFatal);
}

// Test whether it can connect via TCP to a TURN server
// Get a TURN config, and try to get a relay candidate using TCP.
function testTcpConnectivity() {
  Call.asyncCreateTurnConfig(
      function(config) { 
        filterConfig(config, 'tcp');
        gatherCandidates(config, null, Call.isRelay);
      },
      reportFatal);
}

// Test whether it is IPv6 enabled (TODO: test IPv6 to a destination).
// Turn on IPv6, and try to get an IPv6 host candidate.
function testHasIpv6Candidates() {
  var params = { optional: [ { googIPv6: true } ] };
  gatherCandidates(null, params, Call.isIpv6);
}

// Filter the RTCConfiguration |config| to only contain URLs with the
// specified transport protocol |protocol|.
function filterConfig(config, protocol) {
  var transport = 'transport=' + protocol;
  for (var i = 0; i < config.iceServers.length; ++i) {
    var iceServer = config.iceServers[i];
    var newUrls = [];
    for (var j = 0; j < iceServer.urls.length; ++j) {
      if (iceServer.urls[j].indexOf(transport) !== -1) {
        newUrls.push(iceServer.urls[j]);
      }
    }
    iceServer.urls = newUrls;
  }
}

// Create a PeerConnection, and gather candidates using RTCConfig |config|
// and ctor params |params|. Succeed if any candidates pass the |isGood| 
// check, fail if we complete gathering without any passing.
function gatherCandidates(config, params, isGood) {
  var pc = new RTCPeerConnection(config, params);

  // In our candidate callback, stop if we get a candidate that passes |isGood|.
  pc.onicecandidate = function(e) {
    // Once we've decided, ignore future callbacks.
    if (pc.signalingState === 'closed') {
      return;
    }

    if (e.candidate) {
      var parsed = Call.parseCandidate(e.candidate.candidate);
      if (isGood(parsed)) {
        reportSuccess('Gathered candidate with type: ' + parsed.type +
                      ' address: ' + parsed.address);
        pc.close();
        testFinished();
      }
    } else {
      pc.close();
      reportFatal('Failed to gather specified candidates');
    }
  };

  // Create an audio-only, recvonly offer, and setLD with it.
  // This will trigger candidate gathering.
  var createOfferParams = { mandatory: { OfferToReceiveAudio: true } };
  pc.createOffer(function(offer) { pc.setLocalDescription(offer, noop, noop); },
                 noop, createOfferParams);
}

function noop() {
}
