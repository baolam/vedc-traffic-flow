import { useState, useEffect, useCallback } from 'react';

const STORAGE_KEY = 'edgeflow_active_scenario';
const EVENT_NAME = 'edgeflow:scenario-change';
export const DEFAULT_SCENARIO_ID = 'four_intersection_v1';

// Topology contracts that are geographic camera inventories, not a live SUMO/vision operational
// scenario (e.g. hcm_realworld_v1: 793 camera nodes, no per-node telemetry/override UI makes sense).
export const MAP_ONLY_SCENARIOS = ['hcm_realworld_v1'];

export function getActiveScenario() {
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_SCENARIO_ID;
}

// Writes the scenario and notifies every mounted component in this tab synchronously
// (the native 'storage' event only fires in OTHER tabs, which is why every page used to
// drift out of sync until its own next poll/fetch caught up).
export function setActiveScenario(scenarioId) {
  if (!scenarioId || scenarioId === getActiveScenario()) return;
  localStorage.setItem(STORAGE_KEY, scenarioId);
  window.dispatchEvent(new CustomEvent(EVENT_NAME, { detail: scenarioId }));
}

export function useActiveScenario() {
  const [scenarioId, setScenarioIdState] = useState(getActiveScenario);

  useEffect(() => {
    const onChange = (e) => setScenarioIdState(e.detail || getActiveScenario());
    const onStorage = (e) => {
      if (e.key === STORAGE_KEY) setScenarioIdState(e.newValue || DEFAULT_SCENARIO_ID);
    };
    window.addEventListener(EVENT_NAME, onChange);
    window.addEventListener('storage', onStorage);
    return () => {
      window.removeEventListener(EVENT_NAME, onChange);
      window.removeEventListener('storage', onStorage);
    };
  }, []);

  const update = useCallback((next) => setActiveScenario(next), []);

  return [scenarioId, update];
}
