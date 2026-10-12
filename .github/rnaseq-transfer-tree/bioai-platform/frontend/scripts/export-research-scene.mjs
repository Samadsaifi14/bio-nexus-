// Rebuild the original importable scene: node scripts/export-research-scene.mjs
import { writeFile, mkdir } from 'node:fs/promises';
import { GLTFExporter } from 'three/examples/jsm/exporters/GLTFExporter.js';
import { Scene, PerspectiveCamera, DirectionalLight } from 'three';
import { createResearchScene, disposeResearchScene } from '../src/lib/experience/scene.ts';

// GLTFExporter uses the browser FileReader interface to encode buffers.
globalThis.FileReader = class {
  result = null;
  onloadend = null;
  readAsArrayBuffer(blob) { blob.arrayBuffer().then(value => { this.result = value; this.onloadend?.(); }); }
  readAsDataURL(blob) { blob.arrayBuffer().then(value => { this.result = `data:${blob.type};base64,${Buffer.from(value).toString('base64')}`; this.onloadend?.(); }); }
};
const scene = new Scene(); scene.name = 'BioNexus Perspective (illustrative)';
const { root, chapters } = createResearchScene();
// All chapters are separated spatially for import and inspection in Spline.
chapters.forEach((chapter, index) => { chapter.position.x = (index - 1) * 5.5; });
scene.add(root);
const camera = new PerspectiveCamera(36, 1.4, .1, 100); camera.name = 'Overview'; camera.position.z = 20; scene.add(camera);
const key = new DirectionalLight(0xffffff, 3.5); key.position.set(-3, 5, 6); key.name = 'Key';
key.add(key.target); key.target.position.set(0, 0, -1); scene.add(key);
const glb = await new GLTFExporter().parseAsync(scene, { binary: true });
await mkdir('public/scenes', { recursive: true });
await writeFile('public/scenes/bionexus-research.glb', Buffer.from(glb));
disposeResearchScene(root);
console.log(`Exported ${glb.byteLength} bytes: public/scenes/bionexus-research.glb`);
