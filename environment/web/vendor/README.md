# Vendored three.js

three.js version 0.160.0 (r160), MIT licence (see LICENSE), copied from the npm package `three@0.160.0`
so the game runs offline with no build step:

- `three.module.js` from `build/three.module.js`
- `addons/OrbitControls.js` from `examples/jsm/controls/OrbitControls.js`
- `addons/CSS2DRenderer.js` from `examples/jsm/renderers/CSS2DRenderer.js`

The add-ons import from `"three"`; `index.html` maps that name to `./vendor/three.module.js` with an import map.
