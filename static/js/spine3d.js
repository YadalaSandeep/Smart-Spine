/**
 * spine3d.js
 * Renders a simple 3D spine visualization using Three.js
 */

class Spine3D {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        if (!this.container) return;

        this.scene = new THREE.Scene();
        this.camera = new THREE.PerspectiveCamera(75, this.container.clientWidth / this.container.clientHeight, 0.1, 1000);
        this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
        
        this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        this.container.appendChild(this.renderer.domElement);

        // Lighting
        const ambientLight = new THREE.AmbientLight(0xffffff, 0.6);
        this.scene.add(ambientLight);
        const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
        directionalLight.position.set(0, 10, 5);
        this.scene.add(directionalLight);

        // Spine group
        this.spineGroup = new THREE.Group();
        this.vertebrae = [];
        this.segments = 12; // 12 segments representing spine

        const material = new THREE.MeshPhongMaterial({ color: 0x4FD1C5 });

        for (let i = 0; i < this.segments; i++) {
            const geometry = new THREE.CylinderGeometry(0.5, 0.6, 1, 16);
            const mesh = new THREE.Mesh(geometry, material.clone());
            mesh.position.y = (this.segments / 2 - i) * 1.1;
            this.vertebrae.push(mesh);
            this.spineGroup.add(mesh);
        }

        this.scene.add(this.spineGroup);
        this.camera.position.z = 18;

        this.animate();

        // Handle resizing
        this.resize = () => {
            if (!this.container || this.container.clientWidth === 0) return;
            this.camera.aspect = this.container.clientWidth / this.container.clientHeight;
            this.camera.updateProjectionMatrix();
            this.renderer.setSize(this.container.clientWidth, this.container.clientHeight);
        };
        window.addEventListener('resize', this.resize);
    }

    animate() {
        requestAnimationFrame(() => this.animate());
        if (this.container && this.container.clientWidth > 0 && this.renderer.domElement.width === 0) {
             this.resize();
        }
        this.renderer.render(this.scene, this.camera);
    }

    updatePosture(neckTilt, spineLean, shoulderDiff) {
        // Map posture metrics to rotations
        // Neck tilt (head/top segment)
        const neckRotation = (neckTilt / 60) * Math.PI / 4;
        this.vertebrae[0].rotation.x = neckRotation;
        this.vertebrae[1].rotation.x = neckRotation * 0.7;

        // Spine lean (overall group rotation)
        const spineRotation = (spineLean / 60) * Math.PI / 4;
        this.spineGroup.rotation.x = spineRotation;

        // Shoulder diff (z-rotation for lean)
        const shoulderRotation = (shoulderDiff / 20) * Math.PI / 6;
        this.spineGroup.rotation.z = -shoulderRotation;

        // Color coding
        const isBad = Math.abs(neckTilt) > 30 || Math.abs(spineLean) > 20 || Math.abs(shoulderDiff) > 10;
        const color = isBad ? 0xEF4444 : 0x22C55E;

        this.vertebrae.forEach(v => {
            v.material.color.setHex(color);
        });
    }

    setHighlight(isRed) {
        const color = isRed ? 0xEF4444 : 0x22C55E;
        this.vertebrae.forEach(v => {
            v.material.color.setHex(color);
        });
    }
}

// Global instance
window.spineVisualizer = null;
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('spine3dContainer')) {
        window.spineVisualizer = new Spine3D('spine3dContainer');
    }
});
