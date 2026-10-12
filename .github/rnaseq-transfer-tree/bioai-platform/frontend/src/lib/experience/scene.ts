import * as THREE from 'three';

/** Original, illustrative geometry. Never derived from or presented as a scientific result. */
export function createResearchScene() {
  const root = new THREE.Group();
  root.name = 'BioNexus_Story';
  const ink = new THREE.MeshStandardMaterial({ color: '#387c70', roughness: .32, metalness: .16 });
  const sage = new THREE.MeshStandardMaterial({ color: '#a5cabc', roughness: .42, metalness: .08 });
  const pearl = new THREE.MeshStandardMaterial({ color: '#e2ede7', roughness: .35, metalness: .1 });
  const bead = new THREE.SphereGeometry(.115, 12, 8);
  const axis = new THREE.Vector3(0, 1, 0);
  const dna = new THREE.Group(); dna.name = 'Input';
  const strands: THREE.Vector3[][] = [[], []];
  for (let i = 0; i < 36; i++) {
    const t = i / 35;
    const angle = t * Math.PI * 4;
    for (let side = 0; side < 2; side++) {
      const p = new THREE.Vector3(Math.cos(angle + side * Math.PI) * 1.12, (t - .5) * 5.5, Math.sin(angle + side * Math.PI) * 1.12);
      strands[side].push(p);
      const atom = new THREE.Mesh(bead, side ? sage : ink);
      atom.position.copy(p); dna.add(atom);
    }
    if (i % 2 === 0) {
      const a = strands[0][i], b = strands[1][i];
      const bond = new THREE.Mesh(new THREE.CylinderGeometry(.028, .028, a.distanceTo(b), 6), pearl);
      bond.position.copy(a).add(b).multiplyScalar(.5);
      bond.quaternion.setFromUnitVectors(axis, b.clone().sub(a).normalize()); dna.add(bond);
    }
  }
  strands.forEach((points, i) => dna.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 144, .052, 6, false), i ? sage : ink)));
  dna.rotation.z = -.38;

  const analysis = new THREE.Group(); analysis.name = 'Analysis';
  for (let strand = 0; strand < 3; strand++) {
    const points = Array.from({ length: 160 }, (_, i) => {
      const t = i / 159 * Math.PI * 2;
      const r = 1.45 + .42 * Math.cos(3 * t + strand);
      return new THREE.Vector3(r * Math.cos(2 * t), r * Math.sin(2 * t), .85 * Math.sin(3 * t) + (strand - 1) * .26);
    });
    analysis.add(new THREE.Mesh(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points, true), 180, .09, 8, true), [ink, sage, pearl][strand]));
  }
  analysis.rotation.x = -.4;

  const evidence = new THREE.Group(); evidence.name = 'Evidence';
  for (let i = 0; i < 3; i++) {
    const ring = new THREE.Mesh(new THREE.TorusGeometry(1.45 + i * .24, .065, 10, 96), [ink, sage, pearl][i]);
    ring.rotation.set(i * .7, i * .9, .3); evidence.add(ring);
  }
  const core = new THREE.Mesh(new THREE.IcosahedronGeometry(.65, 1), ink); evidence.add(core);
  root.add(dna, analysis, evidence);
  return { root, chapters: [dna, analysis, evidence] };
}

export function disposeResearchScene(root: THREE.Object3D) {
  const geometries = new Set<THREE.BufferGeometry>();
  const materials = new Set<THREE.Material>();
  root.traverse(object => {
    if (object instanceof THREE.Mesh) {
      geometries.add(object.geometry);
      (Array.isArray(object.material) ? object.material : [object.material]).forEach(m => materials.add(m));
    }
  });
  geometries.forEach(g => g.dispose()); materials.forEach(m => m.dispose());
}
