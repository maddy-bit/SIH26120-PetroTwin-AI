# PETRO-TWIN AI: Constrained Multi-Objective Optimization Engine
## Joint CSS + SRP Pareto Optimization, Feasibility Boundaries, and Trade-Off Analysis

---

### 1. The Multi-Objective Mathematical Formulation
Optimizing a heavy oil thermal asset involves competing, mutually antagonistic engineering objectives. Maximizing oil production via excessive steam injection wastes massive capital and burns gas; pumping aggressively at high SPM when the well has cooled snaps rod strings.

The optimization problem is formulated as a **Constrained Multi-Objective Program**:
$$\min_{\mathbf{u}} \mathbf{F}(\mathbf{u}) = \begin{bmatrix}
f_1(\mathbf{u}) = - \hat{Q}_{\text{oil}}(\mathbf{u}) & \text{(Maximize Oil Production)} \\
f_2(\mathbf{u}) = \text{SOR}(\mathbf{u}) & \text{(Minimize Steam-to-Oil Ratio)} \\
f_3(\mathbf{u}) = E_{\text{spec}}(\mathbf{u}) & \text{(Minimize Specific Energy per Bbl)} \\
f_4(\mathbf{u}) = P_{\text{failure}}(\mathbf{u}) & \text{(Minimize Mechanical Failure Risk)}
\end{bmatrix}$$

Subject to decision variables vector:
$$\mathbf{u} = \left[ M_{\text{steam}}, P_{\text{inj}}, t_{\text{soak}}, t_{\text{cutoff}}, S, \text{SPM}, f_{\text{VFD}} \right]^T$$

---

### 2. Physical & Operational Constraints
Every candidate solution $\mathbf{u}$ must pass strict physical, mechanical, and safety boundaries:
1. **Formation Parting Pressure Constraint:**
   $$P_{\text{inj}} \le P_{\text{frac}} \approx 110.0 \text{ bar}$$
2. **Thermal Soak Integrity Constraint:**
   $$2.0 \text{ days} \le t_{\text{soak}} \le 14.0 \text{ days}$$
3. **Pumping Speed Boundaries:**
   $$2.0 \le \text{SPM} \le 10.5 \quad \text{and} \quad 1.5\text{m} \le S \le 3.0\text{m}$$
4. **Structural & Gearbox Load Constraints:**
   $$\text{PPRL}(\mathbf{u}) \le 22,000 \text{ lbs} \quad \text{and} \quad \text{PeakTorque}(\mathbf{u}) \le 320,000 \text{ in-lbs}$$
5. **Rod Floating Zero-Tolerance Boundary:**
   $$v_{\text{max, horsehead}}(\mathbf{u}) < 0.80 \cdot v_{\text{terminal}}(\mu(\mathbf{u})) \quad \text{and} \quad F_{\text{sinking\_margin}} > 250 \text{ lbs}$$

---

### 3. Current Implementation
The checked-in implementation evaluates a finite grid of steam mass, soak duration, stroke, and SPM values. It removes candidates that fail its coded constraints, uses a weighted scalar score to choose one recommendation, and filters feasible candidates for nondominance across production, SOR, energy, and modeled risk. It does not implement LHS, NSGA-II, or SLSQP. Some constraints described here are not currently evaluated by the Python optimizer; see `docs/architecture-audit.md`.
$$\min_{\mathbf{u}} \sum_{i=1}^4 w_i \cdot \frac{f_i(\mathbf{u}) - f_i^{\min}}{f_i^{\max} - f_i^{\min}} + \lambda_{\text{pen}} \cdot \sum_j \max(0, g_j(\mathbf{u}))^2$$

---

### 4. Explainable Pareto Trade-Off Analysis
When an operator selects an AI-recommended operating plan from the Pareto front, the engine dynamically renders the trade-off card:
* **Gains:** e.g., $+18.4\%$ oil production, $-14.2\%$ specific energy.
* **Sacrifices:** e.g., $+0.4$ increase in SOR.
* **Safety Margin:** $+420 \text{ lbs}$ rod downstroke margin; $0\%$ rod-floating risk.
* **Rejected Alternatives:** Explains why higher-production plans were rejected (e.g., *"Plan X was discarded because peak horsehead speed of 1.15 m/s exceeds cold fluid settling speed of 0.82 m/s, triggering rod float and parted rod risk"*).


### 5. Explicit CSS–SRP coupling and execution boundary

Each candidate now calls the same `CoupledCssSrpModel` used by scenario evaluation. The trace passes the steam-mass/soak thermal estimate into production-phase cooling, the resulting production temperature into the viscosity relationship, and the viscosity into SRP load/drag/floating-risk calculations. The scenario API and optimizer response expose the model ID, intermediate stage inputs/outputs, and a representative candidate trace.

The coupling status is always `SIMULATION_ONLY`, `field_eligible=false`, and `NOT_CALIBRATED_ON_FIELD_DATA`. It composes the repository's simplified empirical models; it is not a fully coupled reservoir/wellbore/rod-string simulator. No field recommendation or operating setpoint can be inferred from this trace.

The optimizer remains a finite grid with weighted ranking and nondominated filtering. It checks only the constraints implemented in code. Fracture pressure, gearbox torque and API allowable stress are not evaluated. The “review only” UI action does not dispatch a setpoint.
