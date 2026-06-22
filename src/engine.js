/* engine.js — Decks presentation engine: Fabric.js slide canvas + Reveal.js.
 * SPDX-License-Identifier: GPL-3.0-or-later
 *
 * One Fabric canvas edits the current slide; slide list/order is managed in
 * Python (the libadwaita sidebar). Talks over the suite-common `bridge` channel.
 */
(function () {
  'use strict';

  var SLIDE_W = 960, SLIDE_H = 540;

  function post(msg) {
    try { window.webkit.messageHandlers.bridge.postMessage(msg); }
    catch (e) { console.log('bridge post failed: ' + e); }
  }

  var canvas = null;

  function sampleText() {
    return new fabric.IText('Double-click to edit', {
      left: 80, top: 220, fontSize: 44, fontFamily: 'sans-serif', fill: '#202020'
    });
  }

  function init() {
    canvas = new fabric.Canvas('canvas', { backgroundColor: '#ffffff' });
    canvas.setWidth(SLIDE_W);
    canvas.setHeight(SLIDE_H);
    canvas.add(sampleText());
    canvas.on('object:modified', function () { post({ type: 'changed' }); });
    canvas.on('text:changed', function () { post({ type: 'changed' }); });
    window.__canvas = canvas;

    console.log('Fabric ready: ' + (fabric.version || '?'));
    console.log('Reveal available: ' + (typeof Reveal !== 'undefined'));
    post({ type: 'ready', engine: 'fabric', reveal: (typeof Reveal !== 'undefined') });
  }

  function renderSlideToImage(json, cb) {
    var el = document.createElement('canvas');
    el.width = SLIDE_W; el.height = SLIDE_H;
    var sc = new fabric.StaticCanvas(el, { backgroundColor: '#ffffff' });
    if (json && json.objects) {
      sc.loadFromJSON(json, function () { sc.renderAll(); cb(sc.toDataURL()); });
    } else {
      sc.renderAll(); cb(sc.toDataURL());
    }
  }

  function present(slides) {
    var editor = document.getElementById('editor');
    var revealEl = document.getElementById('reveal');
    var slidesDiv = revealEl.querySelector('.slides');
    slidesDiv.innerHTML = '';
    if (!slides || !slides.length) { slides = [canvas.toJSON()]; }
    var imgs = new Array(slides.length);
    var pending = slides.length;
    slides.forEach(function (s, i) {
      renderSlideToImage(s, function (url) {
        imgs[i] = url;
        if (--pending === 0) { build(imgs); }
      });
    });
    function build(urls) {
      urls.forEach(function (u) {
        var sec = document.createElement('section');
        var im = document.createElement('img');
        im.src = u; im.style.width = '100%'; im.style.height = '100%'; im.style.objectFit = 'contain';
        sec.appendChild(im); slidesDiv.appendChild(sec);
      });
      editor.style.display = 'none';
      revealEl.style.display = 'block';
      if (window.__reveal) { window.__reveal.sync(); window.__reveal.slide(0); }
      else { window.__reveal = new Reveal(revealEl, { width: SLIDE_W, height: SLIDE_H }); window.__reveal.initialize(); }
      console.log('present: ' + urls.length + ' slides');
      post({ type: 'presenting', slides: urls.length });
    }
  }

  function edit() {
    var editor = document.getElementById('editor');
    var revealEl = document.getElementById('reveal');
    revealEl.style.display = 'none';
    editor.style.display = 'flex';
    console.log('edit mode');
  }

  // Python -> JS
  window.bridgeReceive = function (name, data) {
    if (name === 'loadSlide') {
      if (!data || !data.objects) { canvas.clear(); canvas.backgroundColor = '#ffffff'; canvas.renderAll(); }
      else { canvas.loadFromJSON(data, function () { canvas.renderAll(); }); }
    } else if (name === 'getSlide') {
      post({ type: 'slide', data: canvas.toJSON() });
    } else if (name === 'addText') {
      canvas.add(sampleText()); canvas.renderAll(); post({ type: 'changed' });
    } else if (name === 'newSlide') {
      canvas.clear(); canvas.backgroundColor = '#ffffff'; canvas.add(sampleText()); canvas.renderAll();
    } else if (name === 'present') {
      present(data);
    } else if (name === 'edit') {
      edit();
    } else if (name === 'renderAll') {
      var slides = (data && data.length) ? data : [canvas.toJSON()];
      var imgs = new Array(slides.length);
      var pending = slides.length;
      slides.forEach(function (s, i) {
        renderSlideToImage(s, function (url) {
          imgs[i] = url;
          if (--pending === 0) { post({ type: 'rendered', images: imgs }); }
        });
      });
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
