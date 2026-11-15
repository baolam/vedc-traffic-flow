/**
 * FlowTheory Traffic Simulation Engine
 * Based on Cell Transmission Model (CTM) & Multi-Hop Network Control
 * Reflects canonical contracts and src/control/controllers.py FlowTheoryController
 */

export const SATURATION_FLOW_VPS = 0.5; // Q_max (vehicles per second)
export const MIN_GREEN_S = 10;
export const MAX_GREEN_S = 60;
export const YELLOW_S = 3;
export const CRITICAL_OCCUPANCY = 0.90; // When downstream occupancy >= 0.90, receiving capacity drops to 0

// Reproducible PRNG for fair duel comparisons
export class PseudoRandom {
  constructor(seed = 42) {
    this.seed = seed % 2147483647;
    if (this.seed <= 0) this.seed += 2147483646;
  }
  next() {
    this.seed = (this.seed * 16807) % 2147483647;
    return (this.seed - 1) / 2147483646;
  }
}

export class FlowTheorySimulator {
  constructor(options = {}) {
    this.controllerType = options.controllerType || 'flow_theory'; // 'flow_theory' or 'fixed_time'
    this.fixedGreenDuration = options.fixedGreenDuration || 25;
    this.minGreen = options.minGreen || MIN_GREEN_S;
    this.maxGreen = options.maxGreen || MAX_GREEN_S;
    this.yellowDuration = YELLOW_S;
    this.seed = options.seed || 12345;
    this.prng = new PseudoRandom(this.seed);

    this.reset();
  }

  reset() {
    this.simTime = 0;
    this.activePhase = 'J1_PHASE_NS';
    this.phaseState = 'GREEN'; // 'GREEN' or 'YELLOW'
    this.phaseElapsed = 0;
    this.targetPhase = 'J1_PHASE_NS';

    // Approaches state
    this.approaches = {
      'J1_N_IN': { queue: 4, arrivalRate: 0.28, flowIn: 0.25, name: 'Bắc (N_IN)', toNode: 'J3', toEdge: 'E_J1_J3_SB' },
      'J1_S_IN': { queue: 3, arrivalRate: 0.22, flowIn: 0.20, name: 'Nam (S_IN)', toNode: null, toEdge: 'EXIT_NORTH' },
      'J1_E_IN': { queue: 2, arrivalRate: 0.20, flowIn: 0.18, name: 'Đông (E_IN)', toNode: null, toEdge: 'EXIT_WEST' },
      'J1_W_IN': { queue: 3, arrivalRate: 0.22, flowIn: 0.20, name: 'Tây (W_IN)', toNode: 'J2', toEdge: 'E_J1_J2_EB' }
    };

    // Downstream conditions (Graph G=(V,E))
    this.downstreamJ3 = {
      nodeId: 'J3',
      name: 'Nút Hạ Lưu J3',
      occupancy: 0.20,
      twoHopOccupancy: 0.15,
      isSpillbackActive: false,
      capacityVehicles: 20
    };

    this.downstreamJ2 = {
      nodeId: 'J2',
      name: 'Nút Hạ Lưu J2',
      occupancy: 0.15,
      twoHopOccupancy: 0.10,
      isSpillbackActive: false,
      capacityVehicles: 20
    };

    // Vehicles on canvas
    this.vehicles = [];
    this.nextVehicleId = 1;
    this.initVehicles();

    // Intersection center gridlock status
    this.isGridlocked = false;
    this.gridlockIncidents = 0;
    this.gridlockDuration = 0;

    // CTM math metrics log
    this.lastDecisionBreakdown = null;
    this.totalVehiclesCleared = 0;
    this.totalWaitTimeSeconds = 0;
    this.avgWaitTime = 0;
    this.history = [];
  }

  initVehicles() {
    this.vehicles = [];
    // Initial batch of vehicles
    Object.keys(this.approaches).forEach(appId => {
      const q = this.approaches[appId].queue;
      for (let i = 0; i < q; i++) {
        this.vehicles.push({
          id: this.nextVehicleId++,
          approach: appId,
          distToStopLine: 18 + i * 26, // pixels away from stopline
          speed: 0,
          isWaiting: true,
          type: (i % 3 === 0) ? 'bus' : 'car',
          color: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#ec4899'][i % 5]
        });
      }
    });
  }

  // Trigger sudden downstream spillback
  setDownstreamSpillback(active) {
    this.downstreamJ3.isSpillbackActive = active;
    if (active) {
      this.downstreamJ3.occupancy = 0.95;
      this.downstreamJ3.twoHopOccupancy = 0.90;
    } else {
      this.downstreamJ3.occupancy = 0.25;
      this.downstreamJ3.twoHopOccupancy = 0.20;
    }
  }

  // Step simulation forward by dt seconds
  step(dt = 1.0) {
    this.simTime += dt;
    this.phaseElapsed += dt;

    // 1. Generate new arriving vehicles
    this.spawnVehicles(dt);

    // 2. Compute CTM breakdown & Decision
    const breakdown = this.computeFlowTheoryBreakdown();
    this.lastDecisionBreakdown = breakdown;

    // 3. Signal control logic
    if (this.phaseState === 'YELLOW') {
      if (this.phaseElapsed >= this.yellowDuration) {
        this.activePhase = this.targetPhase;
        this.phaseState = 'GREEN';
        this.phaseElapsed = 0;
      }
    } else {
      // Current is GREEN
      let desiredPhase = this.activePhase;
      if (this.controllerType === 'flow_theory') {
        if (this.phaseElapsed >= this.minGreen) {
          if (this.phaseElapsed >= this.maxGreen || breakdown.bestPhase !== this.activePhase) {
            desiredPhase = breakdown.bestPhase;
          }
        }
      } else {
        // Fixed-Time controller
        if (this.phaseElapsed >= this.fixedGreenDuration) {
          desiredPhase = (this.activePhase === 'J1_PHASE_NS') ? 'J1_PHASE_EW' : 'J1_PHASE_NS';
        }
      }

      if (desiredPhase !== this.activePhase) {
        this.phaseState = 'YELLOW';
        this.targetPhase = desiredPhase;
        this.phaseElapsed = 0;
      }
    }

    // 4. Update vehicle movement, queue and gridlock physics
    this.updateVehiclePhysics(dt);

    // 5. Update history for charts
    if (Math.floor(this.simTime) % 1 === 0) {
      const totalQueue = Object.values(this.approaches).reduce((acc, a) => acc + a.queue, 0);
      this.history.push({
        time: Math.round(this.simTime),
        f_NS: Number((breakdown.flows['J1_PHASE_NS'] || 0).toFixed(2)),
        f_EW: Number((breakdown.flows['J1_PHASE_EW'] || 0).toFixed(2)),
        queue: totalQueue,
        throughput: this.totalVehiclesCleared,
        avgWaitTime: Number(this.avgWaitTime.toFixed(1)),
        j3Occupancy: Number((this.downstreamJ3.occupancy * 100).toFixed(0)),
        isGated: breakdown.gatedPhases.includes('J1_PHASE_NS'),
        isGridlocked: this.isGridlocked
      });
      if (this.history.length > 50) this.history.shift();
    }
  }

  // CTM Calculation based on src/control/controllers.py FlowTheoryController
  computeFlowTheoryBreakdown() {
    const qMax = SATURATION_FLOW_VPS;
    const details = {};
    const flows = { 'J1_PHASE_NS': 0, 'J1_PHASE_EW': 0 };
    const gatedPhases = [];

    // North-South Movements
    // Movement 1: J1_N_IN -> J3 (Downstream link E_J1_J3_SB)
    const nApp = this.approaches['J1_N_IN'];
    const sApp = this.approaches['J1_S_IN'];

    // 2-Hop downstream computation: max(occ_1hop, 0.7 * occ_2hop)
    const j3EffectiveOcc = Math.max(this.downstreamJ3.occupancy, 0.7 * this.downstreamJ3.twoHopOccupancy);
    
    // N_IN Sending Capacity
    const n_Sa = Math.min(qMax, (nApp.queue / 10.0) + nApp.flowIn);
    // N_IN Receiving Capacity (CTM Parabolic curve, zero when >= 0.90)
    let n_Rd = 0;
    if (j3EffectiveOcc >= CRITICAL_OCCUPANCY) {
      n_Rd = 0.0; // Anti-Gridlock Gating!
    } else {
      n_Rd = qMax * Math.max(0.0, 1.0 - Math.pow(j3EffectiveOcc / CRITICAL_OCCUPANCY, 2));
    }
    const n_Feff = Math.min(n_Sa, n_Rd);

    // S_IN (Exits network safely, Rd = qMax)
    const s_Sa = Math.min(qMax, (sApp.queue / 10.0) + sApp.flowIn);
    const s_Rd = qMax;
    const s_Feff = Math.min(s_Sa, s_Rd);

    flows['J1_PHASE_NS'] = n_Feff + s_Feff;

    if (j3EffectiveOcc >= CRITICAL_OCCUPANCY) {
      gatedPhases.push('J1_PHASE_NS');
    }

    // East-West Movements
    const eApp = this.approaches['J1_E_IN'];
    const wApp = this.approaches['J1_W_IN'];

    const j2EffectiveOcc = Math.max(this.downstreamJ2.occupancy, 0.7 * this.downstreamJ2.twoHopOccupancy);
    const e_Sa = Math.min(qMax, (eApp.queue / 10.0) + eApp.flowIn);
    const e_Rd = qMax;
    const e_Feff = Math.min(e_Sa, e_Rd);

    const w_Sa = Math.min(qMax, (wApp.queue / 10.0) + wApp.flowIn);
    let w_Rd = (j2EffectiveOcc >= CRITICAL_OCCUPANCY) 
      ? 0.0 
      : qMax * Math.max(0.0, 1.0 - Math.pow(j2EffectiveOcc / CRITICAL_OCCUPANCY, 2));
    const w_Feff = Math.min(w_Sa, w_Rd);

    flows['J1_PHASE_EW'] = e_Feff + w_Feff;

    details['J1_N_IN'] = { Sa: n_Sa, Rd: n_Rd, Feff: n_Feff, downstreamOcc: j3EffectiveOcc, isGated: j3EffectiveOcc >= CRITICAL_OCCUPANCY };
    details['J1_S_IN'] = { Sa: s_Sa, Rd: s_Rd, Feff: s_Feff, downstreamOcc: 0.0, isGated: false };
    details['J1_E_IN'] = { Sa: e_Sa, Rd: e_Rd, Feff: e_Feff, downstreamOcc: 0.0, isGated: false };
    details['J1_W_IN'] = { Sa: w_Sa, Rd: w_Rd, Feff: w_Feff, downstreamOcc: j2EffectiveOcc, isGated: false };

    // Selection
    const bestPhase = (flows['J1_PHASE_NS'] >= flows['J1_PHASE_EW']) ? 'J1_PHASE_NS' : 'J1_PHASE_EW';

    return {
      flows,
      details,
      bestPhase,
      gatedPhases,
      qMax,
      j3EffectiveOcc,
      antiGridlockActive: gatedPhases.length > 0
    };
  }

  spawnVehicles(dt) {
    Object.keys(this.approaches).forEach(appId => {
      const rate = this.approaches[appId].arrivalRate * dt;
      if (this.prng.next() < rate) {
        this.approaches[appId].queue += 1;
        // Find furthest vehicle
        const appVehs = this.vehicles.filter(v => v.approach === appId);
        const maxDist = appVehs.length > 0 ? Math.max(...appVehs.map(v => v.distToStopLine)) : 10;
        this.vehicles.push({
          id: this.nextVehicleId++,
          approach: appId,
          distToStopLine: maxDist + 26,
          speed: 15,
          isWaiting: true,
          type: (this.prng.next() > 0.8) ? 'bus' : 'car',
          color: ['#3b82f6', '#10b981', '#f59e0b', '#8b5cf6', '#06b6d4'][Math.floor(this.prng.next() * 5)]
        });
      }
    });
  }

  updateVehiclePhysics(dt) {
    const isNsGreen = this.activePhase === 'J1_PHASE_NS' && this.phaseState === 'GREEN';
    const isEwGreen = this.activePhase === 'J1_PHASE_EW' && this.phaseState === 'GREEN';

    // Check gridlock conditions:
    // In Fixed-Time mode: if downstream J3 is full (>= 0.90) and NS gets green,
    // vehicles enter the intersection box and stall, causing CROSS-BLOCKING GRIDLOCK!
    if (this.controllerType === 'fixed_time' && this.downstreamJ3.occupancy >= CRITICAL_OCCUPANCY && isNsGreen) {
      this.isGridlocked = true;
      this.gridlockDuration += dt;
      this.gridlockIncidents += 1;
    } else if (this.downstreamJ3.occupancy < CRITICAL_OCCUPANCY) {
      this.isGridlocked = false;
    }

    // Advance vehicles
    const toRemove = [];
    let waitAccumulator = 0;
    let waitingCount = 0;

    Object.keys(this.approaches).forEach(appId => {
      const isGreen = (appId === 'J1_N_IN' || appId === 'J1_S_IN') ? isNsGreen : isEwGreen;
      const appVehs = this.vehicles.filter(v => v.approach === appId).sort((a, b) => a.distToStopLine - b.distToStopLine);

      appVehs.forEach((veh, index) => {
        const leader = (index > 0) ? appVehs[index - 1] : null;
        const targetDist = leader ? leader.distToStopLine + 24 : 0;

        // If green and no obstacle ahead
        const canPass = isGreen && (!leader || leader.distToStopLine < 0) && (!this.isGridlocked || appId === 'J1_N_IN');

        if (veh.distToStopLine <= 4 && !canPass) {
          // Stopped at stop line
          veh.speed = 0;
          veh.isWaiting = true;
          waitAccumulator += dt;
          waitingCount++;
        } else if (leader && veh.distToStopLine <= targetDist) {
          // Queued behind leader
          veh.speed = 0;
          veh.isWaiting = true;
          waitAccumulator += dt;
          waitingCount++;
        } else {
          // Moving forward
          veh.speed = 28;
          veh.distToStopLine -= veh.speed * dt;
          veh.isWaiting = false;

          // Cleared intersection
          if (veh.distToStopLine < -90) {
            toRemove.push(veh.id);
            this.totalVehiclesCleared++;
            if (this.approaches[appId].queue > 0) {
              this.approaches[appId].queue--;
            }
          }
        }
      });
    });

    this.vehicles = this.vehicles.filter(v => !toRemove.includes(v.id));
    this.totalWaitTimeSeconds += waitAccumulator;
    if (this.totalVehiclesCleared + waitingCount > 0) {
      this.avgWaitTime = this.totalWaitTimeSeconds / (this.totalVehiclesCleared + waitingCount);
    }
  }
}
