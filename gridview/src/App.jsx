import { Billboard, OrbitControls } from "@react-three/drei";
import { Canvas, useThree } from "@react-three/fiber";
import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";

import { parseGrd, sameShape } from "../parseGrd.js";
import { buildSurface } from "./mesh.js";

function formatDegrees(value) {
  return value.toFixed(5);
}

function formatMeters(value) {
  const abs = Math.abs(value);
  if (abs >= 1000) return `${(value / 1000).toFixed(2)} км`;
  return `${value.toFixed(abs >= 10 ? 0 : 1)} м`;
}

const PRESETS = [
  {
    id: "volgograd",
    name: "Волгоград",
    detail: "12 × 12 км, 400 × 400, ячейка 30 м",
    terrain: { url: "/samples/volgograd.grd", name: "volgograd.grd" },
    water: { url: "/samples/volgograd-water.grd", name: "volgograd-water.grd" },
  },
];

async function readGrid(file) {
  return { name: file.name, grid: parseGrd(await file.text()) };
}

async function readUrl(url, name) {
  const response = await fetch(url);
  if (!response.ok) throw new Error(`Не удалось открыть ${name}.`);
  return { name, grid: parseGrd(await response.text()) };
}

function Slot({ title, hint, entry, error, onFile, onClear }) {
  return (
    <div
      className="slot"
      onDragOver={(event) => event.preventDefault()}
      onDrop={(event) => {
        event.preventDefault();
        const file = event.dataTransfer.files?.[0];
        if (file) onFile(file);
      }}
    >
      <label>
        <span className="slot-title">{title}</span>
        <span className="slot-name">{entry ? entry.name : hint}</span>
        <input
          type="file"
          accept=".grd,text/plain"
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            if (file) onFile(file);
          }}
        />
      </label>
      {entry ? (
        <button type="button" className="clear" onClick={onClear}>
          Убрать
        </button>
      ) : null}
      {error ? <span className="error">{error}</span> : null}
    </div>
  );
}

function Summary({ entry }) {
  const { grid } = entry;
  return (
    <dl className="facts">
      <div><dt>Узлы</dt><dd>{grid.nx} × {grid.ny}</dd></div>
      <div><dt>Долгота</dt><dd>{formatDegrees(grid.xmin)} … {formatDegrees(grid.xmax)}</dd></div>
      <div><dt>Широта</dt><dd>{formatDegrees(grid.ymin)} … {formatDegrees(grid.ymax)}</dd></div>
      <div><dt>Значения</dt><dd>{grid.zmin.toFixed(2)} … {grid.zmax.toFixed(2)}</dd></div>
      {grid.blanks ? <div><dt>Пустые</dt><dd>{grid.blanks}</dd></div> : null}
    </dl>
  );
}

function Relief({ geometry, exaggeration, wireframe }) {
  if (!geometry.index) return null;
  return (
    <mesh geometry={geometry} scale={[1, exaggeration, 1]}>
      <meshStandardMaterial
        vertexColors
        roughness={0.92}
        metalness={0}
        wireframe={wireframe}
        side={THREE.DoubleSide}
      />
    </mesh>
  );
}

function letterTexture(letter) {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const pen = canvas.getContext("2d");
  pen.clearRect(0, 0, 256, 256);
  pen.fillStyle = "rgba(18, 23, 20, 0.9)";
  pen.beginPath();
  pen.roundRect(16, 56, 224, 144, 28);
  pen.fill();
  pen.fillStyle = "#f7f4ee";
  pen.font = "700 128px sans-serif";
  pen.textAlign = "center";
  pen.textBaseline = "middle";
  pen.fillText(letter, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function PoleLetter({ letter, position, size }) {
  const map = useMemo(() => letterTexture(letter), [letter]);
  return (
    <Billboard position={position}>
      <mesh>
        <planeGeometry args={[size * 1.2, size]} />
        <meshBasicMaterial map={map} transparent depthWrite={false} />
      </mesh>
    </Billboard>
  );
}

function NorthArrow({ width, depth, span }) {
  const y = Math.max(span * 0.12, 24);
  const x = -width / 2 - Math.max(span * 0.02, 12);
  const south = -depth * 0.05;
  const north = depth * 0.42;
  const head = Math.max((north - south) * 0.22, 30);
  const shaftRadius = Math.max(span * 0.006, 3.5);
  const shaft = Math.max(north - south - head, head);
  const letter = Math.max(span * 0.055, 40);
  const beside = span * 0.07;
  return (
    <group position={[x, y, 0]}>
      <mesh position={[0, 0, south + shaft / 2]} rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[shaftRadius, shaftRadius, shaft, 10]} />
        <meshBasicMaterial color="#f4f1e8" />
      </mesh>
      <mesh position={[0, 0, north - head / 2]} rotation={[Math.PI / 2, 0, 0]}>
        <coneGeometry args={[shaftRadius * 3.2, head, 14]} />
        <meshBasicMaterial color="#f4f1e8" />
      </mesh>
      <PoleLetter letter="С" position={[beside, 0, north - head * 0.35]} size={letter} />
      <PoleLetter letter="Ю" position={[beside, 0, south + head * 0.2]} size={letter} />
    </group>
  );
}

function CameraFit({ span }) {
  const camera = useThree((state) => state.camera);
  const controls = useThree((state) => state.controls);
  useEffect(() => {
    camera.position.set(span * 0.28, Math.max(span * 0.55, 40), -span * 1.45);
    camera.near = Math.max(span / 8000, 0.05);
    camera.far = span * 80;
    camera.updateProjectionMatrix();
    camera.lookAt(0, 0, 0);
    if (controls) {
      controls.target.set(0, 0, 0);
      controls.update();
    }
  }, [camera, controls, span]);
  return null;
}

function Stage({ view, exaggeration, wireframe }) {
  const span = view ? Math.max(view.width, view.depth) : 1000;
  return (
    <>
      <color attach="background" args={["#1a211e"]} />
      <hemisphereLight args={["#d5e3ee", "#3a4438", 0.95]} />
      <directionalLight position={[span * 0.45, span * 1.1, span * 0.05]} intensity={1.45} />
      <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -Math.max(span * 0.004, 2), 0]}>
        <planeGeometry args={[span * 1.6, span * 1.6]} />
        <meshStandardMaterial color="#141a17" roughness={1} />
      </mesh>
      {view ? <Relief geometry={view.geometry} exaggeration={exaggeration} wireframe={wireframe} /> : null}
      {view?.geometry.index ? <NorthArrow width={view.width} depth={view.depth} span={span} /> : null}
      <OrbitControls makeDefault enableDamping dampingFactor={0.08} />
      <CameraFit span={span} />
    </>
  );
}

export function App() {
  const [terrain, setTerrain] = useState(null);
  const [water, setWater] = useState(null);
  const [terrainError, setTerrainError] = useState("");
  const [waterError, setWaterError] = useState("");
  const [exaggeration, setExaggeration] = useState(6);
  const [wireframe, setWireframe] = useState(false);
  const [presetId, setPresetId] = useState("");
  const [presetError, setPresetError] = useState("");

  useEffect(() => {
    const block = (event) => event.preventDefault();
    window.addEventListener("dragover", block);
    window.addEventListener("drop", block);
    return () => {
      window.removeEventListener("dragover", block);
      window.removeEventListener("drop", block);
    };
  }, []);

  async function open(file, setEntry, setError) {
    setPresetId("");
    try {
      setEntry(await readGrid(file));
      setError("");
    } catch (error) {
      setEntry(null);
      setError(error.message);
    }
  }

  async function openPreset(preset) {
    setPresetId(preset.id);
    setPresetError("");
    setTerrainError("");
    setWaterError("");
    const [reliefResult, waterResult] = await Promise.allSettled([
      readUrl(preset.terrain.url, preset.terrain.name),
      readUrl(preset.water.url, preset.water.name),
    ]);
    if (reliefResult.status === "fulfilled") setTerrain(reliefResult.value);
    else {
      setTerrain(null);
      setTerrainError(reliefResult.reason.message);
    }
    if (waterResult.status === "fulfilled") setWater(waterResult.value);
    else {
      setWater(null);
      setWaterError(waterResult.reason.message);
    }
    if (reliefResult.status === "rejected" || waterResult.status === "rejected") {
      setPresetError("Не удалось загрузить готовые сетки Волгограда.");
    }
  }

  const aligned = Boolean(terrain && water && sameShape(terrain.grid, water.grid));
  const mismatch = terrain && water && !aligned
    ? `Вода ${water.grid.nx} × ${water.grid.ny}, рельеф ${terrain.grid.nx} × ${terrain.grid.ny}. Для наложения число ячеек должно совпадать.`
    : "";
  const relief = terrain?.grid ?? null;
  const mask = aligned ? water.grid : water && !terrain ? water.grid : null;
  const view = useMemo(() => (relief || mask ? buildSurface(relief, mask) : null), [relief, mask]);
  useEffect(() => () => view?.geometry.dispose(), [view]);
  const span = view ? Math.max(view.width, view.depth) : 0;

  return (
    <div className="app">
      <aside>
        <h1>Сетки Surfer</h1>
        <p className="lead">Рельеф и вода из файлов DSAA. Одинаковое число ячеек ложится на одну поверхность.</p>
        <div className="presets">
          <span className="slot-title">Готовые</span>
          {PRESETS.map((preset) => (
            <button
              key={preset.id}
              type="button"
              className={presetId === preset.id ? "preset selected" : "preset"}
              onClick={() => openPreset(preset)}
            >
              <span>{preset.name}</span>
              <span className="slot-name">{preset.detail}</span>
            </button>
          ))}
          {presetError ? <span className="error">{presetError}</span> : null}
        </div>
        <Slot
          title="Рельеф"
          hint="Выберите или перетащите .grd"
          entry={terrain}
          error={terrainError}
          onFile={(file) => open(file, setTerrain, setTerrainError)}
          onClear={() => { setTerrain(null); setTerrainError(""); setPresetId(""); }}
        />
        {terrain ? <Summary entry={terrain} /> : null}
        <Slot
          title="Вода"
          hint="Необязательно. 0 — вода, 1 — суша"
          entry={water}
          error={waterError}
          onFile={(file) => open(file, setWater, setWaterError)}
          onClear={() => { setWater(null); setWaterError(""); setPresetId(""); }}
        />
        {water ? <Summary entry={water} /> : null}
        {mismatch ? <p className="error">{mismatch}</p> : null}
        {aligned ? <p className="note">Синие ячейки — вода. Остальное окрашено по высоте.</p> : null}
        {view?.thinned ? <p className="note">На экране сетка прорежена до {view.shown[0]} × {view.shown[1]}.</p> : null}
        {view && !view.geometry.index ? <p className="error">В сетке меньше двух рядов или столбцов, поверхность не из чего собрать.</p> : null}
        <label className="slider">
          <span>Вертикальный масштаб ×{exaggeration}</span>
          <input
            type="range"
            min="1"
            max="30"
            value={exaggeration}
            onChange={(event) => setExaggeration(Number(event.target.value))}
          />
        </label>
        <label className="check">
          <input type="checkbox" checked={wireframe} onChange={(event) => setWireframe(event.target.checked)} />
          Каркас
        </label>
        <p className="note">
          {span
            ? `Участок ${formatMeters(view.width)} × ${formatMeters(view.depth)}. Высота отложена от нижней точки. Стрелка указывает с юга на север.`
            : "Первая строка файла — южный край. Пустые узлы Surfer не рисуются."}
        </p>
        <div className="legend">
          <span><i className="swatch water" /> вода</span>
          <span><i className="swatch land" /> суша по высоте</span>
        </div>
      </aside>
      <main>
        {!view ? <p className="empty">Откройте рельеф или маску воды</p> : null}
        <Canvas camera={{ fov: 42, position: [400, 500, -900], near: 0.1, far: 1_000_000 }} dpr={[1, 1.75]}>
          <Stage view={view} exaggeration={exaggeration} wireframe={wireframe} />
        </Canvas>
      </main>
    </div>
  );
}
