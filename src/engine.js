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

  // ── Undo/redo stack ─────────────────────────────────────────────
  var undoStack = [];
  var redoStack = [];
  var MAX_UNDO = 30;

  function saveState() {
    undoStack.push(JSON.stringify(canvas.toJSON()));
    if (undoStack.length > MAX_UNDO) undoStack.shift();
    redoStack = [];
  }

  function undo() {
    if (undoStack.length === 0) return;
    redoStack.push(JSON.stringify(canvas.toJSON()));
    var state = undoStack.pop();
    canvas.loadFromJSON(JSON.parse(state), function () { canvas.renderAll(); });
    post({ type: 'changed' });
  }

  function redo() {
    if (redoStack.length === 0) return;
    undoStack.push(JSON.stringify(canvas.toJSON()));
    var state = redoStack.pop();
    canvas.loadFromJSON(JSON.parse(state), function () { canvas.renderAll(); });
    post({ type: 'changed' });
  }

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
    canvas.on('object:modified', function () { saveState(); post({ type: 'changed' }); });
    canvas.on('text:changed', function () { saveState(); post({ type: 'changed' }); });
    canvas.on('object:added', function () { saveState(); post({ type: 'changed' }); });
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

  function present(slides, transitions) {
    transitions = transitions || [];
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
        if (--pending === 0) { build(imgs, transitions); }
      });
    });
    function build(urls, trs) {
      urls.forEach(function (u, i) {
        var sec = document.createElement('section');
        var tr = trs[i] || 'none';
        if (tr !== 'none') sec.setAttribute('data-transition', tr);
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
    } else if (name === 'applyLayout') {
      canvas.clear(); canvas.backgroundColor = '#ffffff';
      if (data === 'title') {
        canvas.add(new fabric.IText('Title', { left: 80, top: 80, fontSize: 56, fontFamily: 'sans-serif', fontWeight: 'bold', fill: '#202020' }));
        canvas.add(new fabric.IText('Subtitle', { left: 80, top: 180, fontSize: 28, fontFamily: 'sans-serif', fill: '#555' }));
      } else if (data === 'content') {
        canvas.add(new fabric.IText('Title', { left: 80, top: 40, fontSize: 44, fontFamily: 'sans-serif', fontWeight: 'bold', fill: '#202020' }));
        canvas.add(new fabric.IText('Content goes here', { left: 80, top: 130, fontSize: 24, fontFamily: 'sans-serif', fill: '#333' }));
      } else if (data === 'twocol') {
        canvas.add(new fabric.IText('Left', { left: 40, top: 80, fontSize: 28, fontFamily: 'sans-serif', fill: '#202020' }));
        canvas.add(new fabric.IText('Right', { left: 500, top: 80, fontSize: 28, fontFamily: 'sans-serif', fill: '#202020' }));
      }
      canvas.renderAll(); saveState(); post({ type: 'changed' });

    } else if (name === 'addRect') {
      canvas.add(new fabric.Rect({ left: 120, top: 160, width: 220, height: 130,
        fill: '#3584e4', rx: 6, ry: 6 }));
      canvas.renderAll(); post({ type: 'changed' });
    } else if (name === 'newSlide') {
      canvas.clear(); canvas.backgroundColor = '#ffffff'; canvas.add(sampleText()); canvas.renderAll();
    } else if (name === 'present') {
      // Add transitions: data may contain { slides: [...], transitions: [...] }
      var slides = Array.isArray(data) ? data : (data && data.slides) || [canvas.toJSON()];
      var transitions = (data && data.transitions) || [];
      present(slides, transitions);
    } else if (name === 'edit') {
      edit();
    } else if (name === 'undo') {
      undo();
    } else if (name === 'redo') {
      redo();

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
