/**
 * Unit & Behavior Tests for FlowTheory Traffic Simulation Engine
 * Runs via Node.js
 */
import { FlowTheorySimulator, PseudoRandom, CRITICAL_OCCUPANCY, SATURATION_FLOW_VPS } from './flowTheorySimEngine.js';

let passed = 0;
let failed = 0;

function assert(condition, message) {
  if (!condition) {
    console.error(`❌ FAILED: ${message}`);
    failed++;
  } else {
    console.log(`✅ PASSED: ${message}`);
    passed++;
  }
}

console.log("==========================================================");
console.log("  Running FlowTheory Simulation Engine Verification Tests  ");
console.log("==========================================================");

// Test 1: PseudoRandom seed repeatability
{
  const rng1 = new PseudoRandom(12345);
  const rng2 = new PseudoRandom(12345);
  const seq1 = [rng1.next(), rng1.next(), rng1.next()];
  const seq2 = [rng2.next(), rng2.next(), rng2.next()];
  assert(
    JSON.stringify(seq1) === JSON.stringify(seq2),
    "PRNG generates identical sequences for identical seeds (Duel Mode repeatability)"
  );
}

// Test 2: CTM Calculation - Normal Flow
{
  const sim = new FlowTheorySimulator({ controllerType: 'flow_theory', seed: 42 });
  const breakdown = sim.computeFlowTheoryBreakdown();
  assert(breakdown.qMax === SATURATION_FLOW_VPS, `Q_max matches saturation flow ${SATURATION_FLOW_VPS}`);
  assert(breakdown.flows['J1_PHASE_NS'] > 0, "Phase NS has positive effective flow in normal traffic");
  assert(breakdown.flows['J1_PHASE_EW'] > 0, "Phase EW has positive effective flow in normal traffic");
  assert(!breakdown.antiGridlockActive, "Anti-gridlock is inactive under normal occupancy");
}

// Test 3: Downstream Spillback & Anti-Gridlock Gating
{
  const sim = new FlowTheorySimulator({ controllerType: 'flow_theory', seed: 42 });
  sim.setDownstreamSpillback(true);

  const breakdown = sim.computeFlowTheoryBreakdown();
  assert(sim.downstreamJ3.occupancy >= CRITICAL_OCCUPANCY, "Downstream J3 occupancy set to saturated level (0.95)");
  assert(breakdown.gatedPhases.includes('J1_PHASE_NS'), "Phase NS is actively GATED due to downstream blockage");
  assert(breakdown.details['J1_N_IN'].Rd === 0.0, "Receiving capacity Rd for J1_N_IN drops strictly to 0.0");
  assert(breakdown.bestPhase === 'J1_PHASE_EW', "FlowTheory diverts green to Phase EW to protect intersection");
}

// Test 4: Fixed-Time Mode Gridlock Vulnerability vs FlowTheory Zero-Gridlock
{
  const ftSim = new FlowTheorySimulator({ controllerType: 'flow_theory', seed: 100 });
  const fixedSim = new FlowTheorySimulator({ controllerType: 'fixed_time', seed: 100 });

  // Cause spillback on both
  ftSim.setDownstreamSpillback(true);
  fixedSim.setDownstreamSpillback(true);

  // Run 15 simulation seconds
  for (let i = 0; i < 15; i++) {
    ftSim.step(1.0);
    fixedSim.step(1.0);
  }

  assert(
    !ftSim.isGridlocked,
    "FlowTheory avoids intersection gridlock when downstream is jammed (Anti-gridlock protected)"
  );
  assert(
    fixedSim.isGridlocked,
    "Fixed-Time controller succumbs to cross-blocking gridlock when downstream is jammed"
  );
}

// Test 5: Minimum Green Time Constraint
{
  const sim = new FlowTheorySimulator({ controllerType: 'flow_theory', minGreen: 10, seed: 42 });
  // Set current phase to NS, but force EW flow to be much higher
  sim.approaches['J1_E_IN'].queue = 25;
  sim.approaches['J1_W_IN'].queue = 25;
  sim.approaches['J1_N_IN'].queue = 0;
  sim.approaches['J1_S_IN'].queue = 0;

  // Step 3 seconds (less than min_green 10s)
  sim.step(3.0);
  assert(sim.activePhase === 'J1_PHASE_NS', "Controller preserves min green constraint (10s) and does not flicker signal");

  // Step past min_green (total 12 seconds)
  sim.step(9.0);
  assert(sim.phaseState === 'YELLOW' || sim.activePhase === 'J1_PHASE_EW', "Controller transitions phase after min green threshold elapsed");
}

console.log("==========================================================");
console.log(`Results: ${passed} PASSED, ${failed} FAILED`);
console.log("==========================================================");

if (failed > 0) process.exit(1);
