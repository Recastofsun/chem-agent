import { apiCall } from "./core.js";

export async function show(container, formulas) {
  container.innerHTML = `
    <div style="position: relative; width: 100%; height: 400px; background: #000; border-radius: 10px; overflow: hidden;" id="canvas-container">
      <div style="position: absolute; top: 10px; left: 10px; color: white; z-index: 10; font-family: monospace;">
        <h3 style="margin: 0;">${formulas.join(" + ")}</h3>
        <p style="font-size: 12px; color: #aaa;">Вращайте мышкой</p>
      </div>
      <div id="loading-3d" style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: white;">Загрузка 3D...</div>
    </div>
  `;

  const res = await apiCall("get_3d_structures", formulas);
  if (res.status === "error") {
    container.innerHTML = `<p style="color: var(--err)">${res.error.message}</p>`;
    return;
  }

  const molecules = res.data;
  const mount = document.getElementById("canvas-container");
  const loadingEl = document.getElementById("loading-3d");
  if (loadingEl) loadingEl.style.display = "none";

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(75, mount.clientWidth / mount.clientHeight, 0.1, 1000);
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setSize(mount.clientWidth, mount.clientHeight);
  mount.appendChild(renderer.domElement);

  const controls = new THREE.OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.05;

  const light = new THREE.AmbientLight(0xffffff, 0.6);
  scene.add(light);
  const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
  dirLight.position.set(5, 5, 5);
  scene.add(dirLight);

  function createMoleculeGroup(molData) {
    const group = new THREE.Group();
    const atomMeshes = [];
    
    molData.atoms.forEach(a => {
      const geometry = new THREE.SphereGeometry(a.radius, 32, 32);
      const material = new THREE.MeshPhongMaterial({ color: a.color, shininess: 100 });
      const sphere = new THREE.Mesh(geometry, material);
      sphere.position.set(a.x, a.y, a.z);
      group.add(sphere);
      atomMeshes.push(sphere);
    });

    molData.bonds.forEach(b => {
      const start = atomMeshes[b[0]].position;
      const end = atomMeshes[b[1]].position;
      
      const distance = start.distanceTo(end);
      const cylinderGeo = new THREE.CylinderGeometry(0.08, 0.08, distance, 8);
      const cylinderMat = new THREE.MeshPhongMaterial({ color: 0x888888 });
      const cylinder = new THREE.Mesh(cylinderGeo, cylinderMat);
      
      const midPoint = new THREE.Vector3().addVectors(start, end).multiplyScalar(0.5);
      cylinder.position.copy(midPoint);
      cylinder.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), new THREE.Vector3().subVectors(end, start).normalize());
      
      group.add(cylinder);
    });
    
    return group;
  }

  let currentX = 0;
  const spacing = 3.5; // Расстояние между молекулами

  molecules.forEach(mol => {
    const group = createMoleculeGroup(mol);
    
    // Центрируем каждую молекулу в её локальных координатах
    const box = new THREE.Box3().setFromObject(group);
    const center = box.getCenter(new THREE.Vector3());
    group.position.sub(center); 
    
    // Смещаем молекулу вправо
    group.position.x += currentX;
    scene.add(group);
    
    // Вычисляем ширину молекулы для отступа следующей
    const size = box.getSize(new THREE.Vector3());
    currentX += size.x + spacing;
  });

  // Центрируем всю сцену (сдвигаем камеру так, чтобы всё было видно)
  const fullBox = new THREE.Box3().setFromObject(scene);
  const fullCenter = fullBox.getCenter(new THREE.Vector3());
  const fullSize = fullBox.getSize(new THREE.Vector3());
  const maxDim = Math.max(fullSize.x, fullSize.y, fullSize.z);
  
  camera.position.set(fullCenter.x, fullCenter.y, fullCenter.z + maxDim * 1.2);
  controls.target.copy(fullCenter);
  controls.update();

  function animate() {
    requestAnimationFrame(animate);
    controls.update();
    renderer.render(scene, camera);
  }
  animate();
}