# 🏎️ Realtime 4‑Stroke Engine Simulator & 3‑D Visualizer

A Streamlit web‑app that couples **thermodynamic performance calculations** with a **PyVista 3‑D slider‑crank animation**.  
Change any parameter—bore, stroke, RPM, boost, ambient conditions—and both the numeric gauges *and* the engine model update in real time.

---

## Table of Contents
1. [Key Features](#key-features)  
2. [Quick Start](#quick-start)  
3. [Folder Structure](#folder-structure)  
4. [Physics Model](#physics-model)  
5. [Code Walk‑Through](#code-walk-through)  
6. [Calibration & Tuning](#calibration-and-tuning)  
7. [Typical Use Cases](#typical-use-cases)  
8. [Road‑map](#roadmap)  
9. [References](#references)  
10. [License](#license)

---

## Key Features

| Domain | Highlights |
|--------|------------|
| **Thermodynamics** | • Skewed‑Gaussian volumetric‑efficiency curve<br>• BSFC map linked to VE peak<br>• Watson–Heywood FMEP for mechanical η<br>• Computes HP, Torque, BMEP, IMEP, BSFC, brake‑thermal η, etc. |
| **Environment & Load** | • ISA altitude & ambient‑temperature sliders<br>• Fuel selector (Gasoline / Diesel / E85) swaps LHV & AFR<br>• Boost and throttle scalers |
| **3‑D Visualiser** | • Metric scaling (mm → m) for true proportions<br>• Dynamic connecting‑rod geometry<br>• Free‑orbit WebGL canvas with eye‑dome lighting |
| **UI** | • Streamlit metric panel (HP, Torque, BMEP, efficiencies)<br>• Collapsible “Detailed Specs” section<br>• Hooks for live BMEP‑vs‑RPM plot |
| **Extensibility** | • CSV lookup for real VE/BSFC maps<br>• Clean helper module for ISA density<br>• Clearly marked TODOs for valve/cam kinematics and turbo maps |

---

## Quick Start

```bash
git clone https://github.com/your-handle/engine-sim.git
cd engine-sim
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\Activate
pip install -r requirements.txt
streamlit run app.py
```

Browse to <http://localhost:8501> and start dragging sliders.

---

## Folder Structure

```
├── app.py                   # Streamlit UI glue
├── engine_simulator.py      # All thermodynamic maths
├── engine_visualizer_3d.py  # PyVista scene builder
├── engine_visualizer.py     # 2D scene builder
├── helpers
│   └── isa.py               # Mini ISA density helper
├── maps
│   └── ve_bsfc.csv          # Optional VE/BSFC lookup table
├── assets
│   └── brushed_metal.png    # shader
└── README.md
```

---

## Physics Model

### 1 · Volumetric Efficiency

$$
\eta_v(\mathrm{RPM}) = 0.60 + 0.40\,
\begin{cases}
\displaystyle \exp\!\left[-\tfrac{1}{2}\left(\tfrac{\mathrm{RPM}-R_{pk}}{\sigma_{\text{low}}}\right)^2\right], & \text{RPM} < R_{pk} \\
\displaystyle \exp\!\left[-\tfrac{1}{2}\left(\tfrac{\mathrm{RPM}-R_{pk}}{\sigma_{\text{high}}}\right)^2\right], & \text{RPM} \ge R_{pk}
\end{cases}
$$

with  

$$R_{pk}=0.6\,RPM_{red},\qquad
\sigma_{\text{low}}=0.25\,R_{pk},\qquad
\sigma_{\text{high}}=0.18\,R_{pk}.$$

### 2 · Mass Flow  

$$
\dot m_\text{air}= \frac{RPM}{120}\,V_d\,\rho_\text{air}\,\eta_v,
\qquad
\dot m_\text{fuel}= \frac{\dot m_\text{air}}{AFR}
$$

*(four‑stroke ⇒ rev s⁻¹ = RPM / 60, then ÷ 2).*

### 3 · Brake Power & Torque  

$$
BSFC = BSFC_{nom}\,[1-0.10\,(\eta_v-0.60)]
$$

$$
P_b=\frac{\dot m_\text{fuel}}{BSFC},
\qquad
\tau = \frac{P_b}{\omega},
\quad
\omega=\frac{2\pi\,RPM}{60}
$$

### 4 · Mechanical Losses  

Watson–Heywood friction mean effective pressure:

$$
FMEP = A + B\,RPM + C\,RPM^2
$$

*(defaults&nbsp;A = 30 kPa, B = 1.5, C = 2 × 10⁻⁴)*


$$
\eta_\text{mech}=1-\frac{FMEP\,V_d\,RPM/120}{P_b}
$$

### 5 · Thermal Efficiencies  

$$
\eta_\text{bth}= \frac{P_b}{\dot m_\text{fuel}\,LHV},
\qquad
\eta_\text{otto}= 1-\frac{1}{CR^{\gamma-1}}
$$

### 6 · Mean Effective Pressures  

$$
BMEP=\frac{2\pi\,\tau}{V_d},
\qquad
IMEP=\frac{BMEP}{\eta_\text{mech}}
$$

---

## Code Walk Through

| File | Purpose | Key entry‑points |
|------|---------|------------------|
| **`engine_simulator.py`** | Numerical core | `EngineSimulator._calculate_performance()` – pure, stateless maths; unit‑test friendly |
| **`engine_visualizer_3d.py`** | 3‑D model | `EngineVisualizer3D.build_scene()` – rebuilds meshes; geometry metric‑scaled |
| **`app.py`** | UI orchestration | Sidebar widgets → update engine → render metrics + 3‑D |

---

## Calibration and Tuning

| Goal | Parameter(s) | Typical range |
|------|--------------|---------------|
| Lower idle BSFC | `BSFC_nom` | 260–320 g/kWh (SI) |
| Softer high‑rpm fall‑off | `σ_high` | 0.18 → 0.25 × R<sub>pk</sub> |
| More aggressive cam | `σ_low` ↓ | 0.25 → 0.15 × R<sub>pk</sub> |
| Heavier diesel friction | `FMEP_A/B/C` ↑ | 50 kPa / 2.5 / 4e‑4 |

---

## Typical Use Cases

1. **Lecture demos** – illustrate how VE, AFR, or boost shape the torque curve in real time.  
2. **Concept feasibility** – sanity‑check bore‑stroke combos before detailed GT‑POWER sims.  
3. **Test‑cell dashboards** – feed live MAF + RPM into the model to estimate BMEP on the fly.  
4. **Marketing widget** – embed the 3‑D model on a product page for interactive specs.

---

## Roadmap

| Milestone | Status |
|-----------|--------|
| CSV VE/BSFC map support | ☐ |
| Full valve & cam animation | ☐ |
| Wiebe heat‑release → cylinder pressure | ☐ |
| Turbo map with compressor‑η islands | ☐ |
| Export power/torque curve (CSV/PDF) | ☐ |

---

## References

* Heywood, J. B. **_Internal Combustion Engine Fundamentals_**, 2e, McGraw‑Hill, 2018  
* Watson, N. & Janota, M. **_Turbocharging the Internal Combustion Engine_**, Macmillan, 1982  
* **SAE J1349** – Engine power test code  
* **ISO 2534** – Fuel consumption & BSFC definitions

---

## License

Distributed under the MIT License. See [`LICENSE`](LICENSE) for details.

## 📞 Contact

- **Author:** Daglar Duman
- **Project Link:** [https://github.com/daglar510/Engine_sim](https://github.com/daglar510/Engine_sim) 
