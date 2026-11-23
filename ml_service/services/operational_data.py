"""Validated operational cycle, event, SRP, and measurement-link services."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from typing import Any
from ml_service.services.data_ingestion import BOUNDS
from ml_service.services.physics_execution import PARAMETER_RANGES


QUANTITIES = {
    "injection_mass_tons": {"metric_ton"}, "steam_quality": {"fraction"},
    "injection_pressure_bar": {"bar"}, "injection_temperature_c": {"°C"},
    "enthalpy_kj_kg": {"kJ/kg"}, "steam_energy_gj": {"GJ"},
    "stroke_length_m": {"m"}, "spm": {"stroke/min"}, "pump_depth_m": {"m"},
    "plunger_diameter_mm": {"mm"}, "rod_outer_diameter_mm": {"mm"},
    "rod_inner_diameter_mm": {"mm"}, "tubing_id_mm": {"mm"},
    "fluid_level_m": {"m"}, "pump_intake_pressure_bar": {"bar"},
    "pump_discharge_pressure_bar": {"bar"}, "oil_rate_bpd": {"bbl/day"},
    "runtime_hours": {"hour"}, "downtime_hours": {"hour"},
    "pump_efficiency_fraction": {"fraction"}, "dynamometer_min_load_n": {"N"},
    "dynamometer_max_load_n": {"N"}, "viscosity_cp": {"cP"},
    "fluid_density_kg_m3": {"kg/m3"}, "rod_weight_air_n": {"N"},
    "steel_density_kg_m3": {"kg/m3"}, "pump_fillage_fraction": {"fraction"},
}
EVENT_TYPES = {
    "CSS_INJECTION", "CSS_SOAK", "PRODUCTION_RESTART", "SRP_CONFIGURATION_CHANGE",
    "PUMP_REPLACEMENT", "WORKOVER", "MAINTENANCE", "SHUTDOWN", "RESTART",
    "PRODUCTION_INTERRUPTION", "EQUIPMENT_FAILURE", "OPERATOR_INTERVENTION",
}
QUALITY = {"VALID", "SUSPECT"}
QUANTITY_BOUNDS = {"injection_mass_tons":(0,10_000_000),"steam_quality":(0,1),"injection_pressure_bar":(0,2000),"injection_temperature_c":(-50,600),"enthalpy_kj_kg":(0,5000),"steam_energy_gj":(0,1e9),
    "stroke_length_m":(0,20),"spm":(0,60),"pump_depth_m":PARAMETER_RANGES["pump_depth_m"],"plunger_diameter_mm":PARAMETER_RANGES["plunger_diameter_mm"],"rod_outer_diameter_mm":PARAMETER_RANGES["rod_outer_diameter_mm"],"rod_inner_diameter_mm":(0,500),
    "tubing_id_mm":PARAMETER_RANGES["tubing_id_mm"],"fluid_level_m":(0,20000),"pump_intake_pressure_bar":(0,2000),"pump_discharge_pressure_bar":(0,2000),"oil_rate_bpd":BOUNDS["oil_rate_bpd"],
    "runtime_hours":(0,8760),"downtime_hours":(0,8760),"pump_efficiency_fraction":(0,1),"dynamometer_min_load_n":(0,1e9),"dynamometer_max_load_n":(0,1e9),
    "viscosity_cp":BOUNDS["viscosity_cp"],"fluid_density_kg_m3":PARAMETER_RANGES["fluid_density_kg_m3"],"rod_weight_air_n":PARAMETER_RANGES["rod_weight_air_n"],"steel_density_kg_m3":PARAMETER_RANGES["steel_density_kg_m3"],"pump_fillage_fraction":(0,1)}


def _time(value: Any, field: str, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    try:
        parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _fingerprint(record: dict[str, Any]) -> str:
    clean = {key: value for key, value in record.items() if key not in {"cycle_id", "event_id", "record_id", "created_at", "fingerprint"}}
    return hashlib.sha256(json.dumps(clean, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class OperationalDataService:
    def __init__(self, repository):
        self.repository = repository

    def _known_well(self, well_id: str) -> None:
        if not isinstance(well_id, str) or not well_id.strip() or self.repository.get_well(well_id) is None:
            raise ValueError("Unknown well_id")

    @staticmethod
    def _quantity(name: str, value: Any, *, optional: bool = True) -> dict[str, Any] | None:
        if value is None and optional:
            return None
        if not isinstance(value, dict) or set(value) - {"value", "unit", "quality_status", "provenance"} or not {"value", "unit"} <= set(value):
            raise ValueError(f"{name} must contain value and unit")
        amount = value["value"]
        if isinstance(amount, bool) or not isinstance(amount, (int, float)) or not math.isfinite(float(amount)):
            raise ValueError(f"{name}.value must be finite")
        if value["unit"] not in QUANTITIES[name]:
            raise ValueError(f"{name}.unit must be one of {sorted(QUANTITIES[name])}")
        low,high=QUANTITY_BOUNDS[name]
        if not low <= float(amount) <= high: raise ValueError(f"{name}.value must be between {low} and {high} {value['unit']}")
        quality = value.get("quality_status", "VALID")
        if quality not in QUALITY:
            raise ValueError(f"{name}.quality_status must be VALID or SUSPECT")
        provenance=value.get("provenance",{})
        if not isinstance(provenance,dict): raise ValueError(f"{name}.provenance must be an object")
        return {"value": float(amount), "unit": value["unit"], "quality_status": quality,"provenance": provenance}

    def validate_cycle(self, source: dict[str, Any]) -> dict[str, Any]:
        allowed = {"schema_version","cycle_id", "well_id", "cycle_number", "injection_start", "injection_end", "injection_duration_minutes",
                   "injection_mass_tons", "steam_quality", "injection_pressure_bar", "injection_temperature_c", "enthalpy_kj_kg", "steam_energy_gj",
                   "soak_start", "soak_end", "production_restart", "post_soak_observation_start", "post_soak_observation_end",
                   "configuration_id", "model_version", "source", "provenance", "quality_status", "metadata"}
        extra = set(source) - allowed
        if extra:
            raise ValueError(f"Unsupported CSS cycle fields: {', '.join(sorted(extra))}")
        if source.get("schema_version","1.0")!="1.0": raise ValueError("schema_version must be 1.0")
        well_id = source.get("well_id"); self._known_well(well_id)
        number = source.get("cycle_number")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            raise ValueError("cycle_number must be a positive integer")
        times = {name: _time(source.get(name), name, optional=True) for name in
                 ("injection_start", "injection_end", "soak_start", "soak_end", "production_restart", "post_soak_observation_start", "post_soak_observation_end")}
        ordered = [times[name] for name in ("injection_start", "injection_end", "soak_start", "soak_end", "production_restart", "post_soak_observation_start", "post_soak_observation_end") if times[name] is not None]
        if any(datetime.fromisoformat(b) < datetime.fromisoformat(a) for a, b in zip(ordered, ordered[1:])):
            raise ValueError("CSS events must follow injection → soak → production → post-soak observation chronology")
        explicit_duration = source.get("injection_duration_minutes")
        computed_duration = None
        if times["injection_start"] and times["injection_end"]:
            computed_duration = (datetime.fromisoformat(times["injection_end"]) - datetime.fromisoformat(times["injection_start"])).total_seconds() / 60
        if explicit_duration is not None and (isinstance(explicit_duration,bool) or not isinstance(explicit_duration, (int, float)) or not math.isfinite(float(explicit_duration)) or explicit_duration < 0 or (computed_duration is not None and abs(explicit_duration - computed_duration) > 1e-6)):
            raise ValueError("injection_duration_minutes must be nonnegative and agree with the supplied timestamps")
        quality = source.get("quality_status", "VALID")
        if quality not in QUALITY:
            raise ValueError("quality_status must be VALID or SUSPECT")
        provenance=source.get("provenance", {})
        if not isinstance(provenance,dict) or not provenance or not isinstance(source.get("source"),str) or not source["source"].strip():
            raise ValueError("source and non-empty provenance are required")
        metadata=source.get("metadata",{})
        if not isinstance(metadata,dict): raise ValueError("metadata must be an object")
        labels=metadata.get("operating_regime_labels")
        if labels is not None and (not isinstance(labels,list) or any(not isinstance(label,str) or not label.strip() for label in labels)): raise ValueError("operating_regime_labels must be an explicit array of non-empty strings")
        configuration_id=source.get("configuration_id")
        if configuration_id:
            configuration=self.repository.get_physical_configuration_by_id(configuration_id)
            if configuration is None or configuration["well_id"] != well_id: raise ValueError("configuration_id must reference a persisted configuration for this well")
        record = {"schema_version":"1.0","well_id": well_id, "cycle_number": number, "status": "COMPLETE" if all(times[n] for n in ("injection_start", "injection_end", "soak_start", "soak_end", "production_restart")) else "INCOMPLETE",
                  **times, "injection_duration_minutes": computed_duration if computed_duration is not None else explicit_duration,
                  "quantities": {name: self._quantity(name, source.get(name)) for name in ("injection_mass_tons", "steam_quality", "injection_pressure_bar", "injection_temperature_c", "enthalpy_kj_kg", "steam_energy_gj")},
                  "configuration_id": configuration_id, "model_version": source.get("model_version"),
                  "source": source.get("source"), "provenance": provenance, "quality_status": quality,
                  "metadata": metadata}
        for quantity in record["quantities"].values():
            if quantity is not None and not quantity["provenance"]: quantity["provenance"]={"record_source":record["source"],**provenance}
        present_phases = sum(times[n] is not None for n in ("injection_start", "soak_start", "production_restart"))
        record["completeness"] = {"status": record["status"], "phases_present": present_phases, "phases_required": 3,
            "missing_fields": [name for name in ("injection_start", "injection_end", "soak_start", "soak_end", "production_restart") if not times[name]],
            "missing_operational_inputs": [name for name in ("injection_mass_tons", "injection_pressure_bar", "injection_temperature_c") if record["quantities"][name] is None]}
        record["fingerprint"] = _fingerprint(record)
        if source.get("cycle_id"): record["cycle_id"] = source["cycle_id"]
        return record

    def create_css_cycle(self, source: dict[str, Any]) -> dict[str, Any]:
        return self.repository.save_css_cycle(self.validate_cycle(source))

    def update_css_cycle(self, cycle_id: str, source: dict[str, Any]) -> dict[str, Any] | None:
        if self.repository.get_css_cycle(cycle_id) is None: return None
        source = {**source, "cycle_id": cycle_id}
        return self.repository.save_css_cycle(self.validate_cycle(source), update=True)

    def validate_event(self, source: dict[str, Any]) -> dict[str, Any]:
        allowed={"schema_version","event_id","well_id","cycle_id","event_type","occurred_at","ended_at","external_id","source","provenance","quality_status","metadata"}
        if set(source)-allowed: raise ValueError(f"Unsupported event fields: {', '.join(sorted(set(source)-allowed))}")
        if source.get("schema_version","1.0")!="1.0": raise ValueError("schema_version must be 1.0")
        well_id=source.get("well_id"); self._known_well(well_id)
        event_type=source.get("event_type")
        if event_type not in EVENT_TYPES: raise ValueError(f"event_type must be one of {sorted(EVENT_TYPES)}")
        occurred=_time(source.get("occurred_at"),"occurred_at"); ended=_time(source.get("ended_at"),"ended_at",True)
        if ended and ended < occurred: raise ValueError("ended_at must not precede occurred_at")
        cycle_id=source.get("cycle_id")
        if cycle_id:
            cycle=self.repository.get_css_cycle(cycle_id)
            if cycle is None or cycle["well_id"] != well_id: raise ValueError("cycle_id must reference a CSS cycle belonging to this well")
            expected={"CSS_INJECTION":("injection_start","injection_end"),"CSS_SOAK":("soak_start","soak_end"),"PRODUCTION_RESTART":("production_restart","production_restart")}.get(event_type)
            if expected:
                expected_start,expected_end=(cycle.get(name) for name in expected)
                if expected_start and occurred != expected_start: raise ValueError(f"{event_type} occurred_at conflicts with linked cycle chronology")
                if ended and expected_end and ended != expected_end: raise ValueError(f"{event_type} ended_at conflicts with linked cycle chronology")
        quality=source.get("quality_status","VALID")
        if quality not in QUALITY: raise ValueError("quality_status must be VALID or SUSPECT")
        provenance=source.get("provenance",{})
        if not isinstance(provenance,dict) or not provenance or not isinstance(source.get("source"),str) or not source["source"].strip(): raise ValueError("source and non-empty provenance are required")
        metadata=source.get("metadata",{})
        if not isinstance(metadata,dict): raise ValueError("metadata must be an object")
        labels=metadata.get("operating_regime_labels")
        if labels is not None and (not isinstance(labels,list) or any(not isinstance(label,str) or not label.strip() for label in labels)): raise ValueError("operating_regime_labels must be an explicit array of non-empty strings")
        record={"schema_version":"1.0","well_id":well_id,"cycle_id":cycle_id,"event_type":event_type,"occurred_at":occurred,"ended_at":ended,
                "external_id":source.get("external_id"),"source":source.get("source"),"provenance":provenance,
                "quality_status":quality,"metadata":metadata}
        record["fingerprint"]=_fingerprint(record)
        if source.get("event_id"): record["event_id"]=source["event_id"]
        return record

    def create_event(self, source: dict[str, Any]) -> dict[str, Any]: return self.repository.save_operational_event(self.validate_event(source))

    def validate_srp_record(self, source: dict[str, Any]) -> dict[str, Any]:
        allowed={"schema_version","record_id","well_id","record_type","valid_at","valid_from","valid_to","external_id","parameters","observations","source","provenance","quality_status","metadata"}
        if set(source)-allowed: raise ValueError(f"Unsupported SRP record fields: {', '.join(sorted(set(source)-allowed))}")
        if source.get("schema_version","1.0")!="1.0": raise ValueError("schema_version must be 1.0")
        well_id=source.get("well_id"); self._known_well(well_id)
        record_type=source.get("record_type")
        if record_type not in {"CONFIGURATION","OPERATING_OBSERVATION","INTERVENTION"}: raise ValueError("record_type must be CONFIGURATION, OPERATING_OBSERVATION, or INTERVENTION")
        valid_at=_time(source.get("valid_at"),"valid_at",optional=True)
        valid_from=_time(source.get("valid_from"),"valid_from",optional=True); valid_to=_time(source.get("valid_to"),"valid_to",optional=True)
        if valid_at is None and valid_from is None: raise ValueError("valid_at or valid_from is required")
        if valid_to and valid_from and valid_to < valid_from: raise ValueError("valid_to must not precede valid_from")
        params=source.get("parameters")
        if not isinstance(params,dict) or not params: raise ValueError("parameters must be a non-empty map of named quantities")
        unknown=set(params)-set(QUANTITIES)
        if unknown: raise ValueError(f"Unsupported SRP parameters: {', '.join(sorted(unknown))}")
        normalized={name:self._quantity(name,value,optional=False) for name,value in params.items()}
        quality=source.get("quality_status","VALID")
        if quality not in QUALITY: raise ValueError("quality_status must be VALID or SUSPECT")
        provenance=source.get("provenance",{})
        if not isinstance(provenance,dict) or not provenance or not isinstance(source.get("source"),str) or not source["source"].strip(): raise ValueError("source and non-empty provenance are required")
        for quantity in normalized.values():
            if not quantity["provenance"]: quantity["provenance"]={"record_source":source["source"],**provenance}
        observations=source.get("observations",[])
        if not isinstance(observations,list): raise ValueError("observations must be an array")
        normalized_observations=[]
        for observation in observations:
            if not isinstance(observation,dict) or observation.get("type")!="DYNAMOMETER_CARD": raise ValueError("Only typed DYNAMOMETER_CARD observations are currently supported")
            measured_at=_time(observation.get("measured_at"),"dynamometer measured_at")
            if observation.get("load_unit")!="N" or not isinstance(observation.get("points"),list) or len(observation["points"])<2: raise ValueError("DYNAMOMETER_CARD requires at least two points with load_unit N")
            for point in observation["points"]:
                if not isinstance(point,dict) or not isinstance(point.get("position_deg"),(int,float)) or not isinstance(point.get("load_n"),(int,float)) or not all(math.isfinite(float(point[key])) for key in ("position_deg","load_n")): raise ValueError("DYNAMOMETER_CARD points require finite position_deg and load_n")
            card_quality=observation.get("quality_status","VALID"); card_provenance=observation.get("provenance",provenance)
            if card_quality not in QUALITY or not isinstance(card_provenance,dict) or not card_provenance: raise ValueError("Invalid DYNAMOMETER_CARD quality/provenance")
            normalized_observations.append({**observation,"measured_at":measured_at,"quality_status":card_quality,"provenance":card_provenance,"points":[{"position_deg":float(point["position_deg"]),"load_n":float(point["load_n"])} for point in observation["points"]]})
        metadata=source.get("metadata",{})
        if not isinstance(metadata,dict): raise ValueError("metadata must be an object")
        record={"schema_version":"1.0","well_id":well_id,"record_type":record_type,"valid_at":valid_at or valid_from,"valid_from":valid_from,"valid_to":valid_to,
                "external_id":source.get("external_id"),"parameters":normalized,"observations":normalized_observations,"source":source.get("source"),"provenance":provenance,
                "quality_status":quality,"metadata":metadata}
        record["fingerprint"]=_fingerprint(record)
        if source.get("record_id"): record["record_id"]=source["record_id"]
        return record

    def create_srp_record(self, source: dict[str, Any]) -> dict[str, Any]: return self.repository.save_srp_record(self.validate_srp_record(source))

    def link_measurement(self, entity_type: str, entity_id: str, measurement_id: str, relation: str) -> dict[str, Any]:
        if entity_type not in {"css_cycle","operational_event","srp_record"}: raise ValueError("Unsupported entity_type")
        if not isinstance(relation,str) or not relation.strip(): raise ValueError("relation is required")
        record=(self.repository.get_css_cycle(entity_id) if entity_type=="css_cycle" else self.repository.get_operational_event(entity_id) if entity_type=="operational_event" else self.repository.get_srp_record(entity_id))
        if record is None: raise ValueError("Operational record not found")
        measurement=next((row for row in self.repository.query_measurements(record["well_id"],limit=10000) if row["measurement_id"]==measurement_id),None)
        if measurement is None: raise ValueError("Measurement must exist and belong to the same well")
        existing=self.repository.list_measurement_links(well_id=record["well_id"])
        if entity_type=="css_cycle" and any(x["entity_type"]=="css_cycle" and x["measurement_id"]==measurement_id and x["entity_id"]!=entity_id for x in existing):
            raise ValueError("Measurement is already associated with a different CSS cycle")
        return self.repository.link_measurement(record["well_id"],entity_type,entity_id,measurement_id,relation.strip())

    def timeline(self, well_id: str, start_at: str | None = None, end_at: str | None = None) -> dict[str, Any]:
        self._known_well(well_id)
        start_at=_time(start_at,"start_at",True) if start_at else None; end_at=_time(end_at,"end_at",True) if end_at else None
        if start_at and end_at and end_at<start_at: raise ValueError("end_at must not precede start_at")
        cycles=self.repository.list_css_cycles(well_id); events=self.repository.list_operational_events(well_id,start_at=start_at,end_at=end_at); srp=self.repository.list_srp_records(well_id,start_at=start_at,end_at=end_at)
        if start_at:
            cycles=[x for x in cycles if (x.get("injection_start") or x["created_at"])>=start_at]
        if end_at:
            cycles=[x for x in cycles if (x.get("injection_start") or x["created_at"])<=end_at]
        links=self.repository.list_measurement_links(well_id=well_id)
        entries=[]
        for cycle in cycles: entries.append({"entry_type":"css_cycle","occurred_at":cycle.get("injection_start") or cycle["created_at"],"record":cycle,"links":[x for x in links if x["entity_type"]=="css_cycle" and x["entity_id"]==cycle["cycle_id"]]})
        for event in events: entries.append({"entry_type":"event","occurred_at":event["occurred_at"],"record":event,"links":[x for x in links if x["entity_type"]=="operational_event" and x["entity_id"]==event["event_id"]]})
        for record in srp: entries.append({"entry_type":"srp_record","occurred_at":record["valid_at"],"record":record,"links":[x for x in links if x["entity_type"]=="srp_record" and x["entity_id"]==record["record_id"]]})
        entries.sort(key=lambda x:(x["occurred_at"],x["entry_type"]))
        regime_labels=sorted({label for item in cycles+events+srp for label in item.get("metadata",{}).get("operating_regime_labels",[])})
        return {"well_id":well_id,"entries":entries,"operating_regime":{"status":"EXPLICIT_LABELS_AVAILABLE" if regime_labels else "UNAVAILABLE_UNLESS_EXPLICITLY_LABELED","labels":regime_labels,"reason":"The service does not infer operating regimes; only source-supplied labels are returned."},"data_quality":{"css_cycles":len(cycles),"incomplete_css_cycles":sum(x["status"]!="COMPLETE" for x in cycles),"suspect_events":sum(x["quality_status"]!="VALID" for x in events),"srp_records":len(srp)}}

    def calibration_readiness(self, well_id: str) -> dict[str, Any]:
        self._known_well(well_id)
        cycles=[x for x in self.repository.list_css_cycles(well_id) if not x.get("archived_at")]; events=[x for x in self.repository.list_operational_events(well_id) if not x.get("archived_at")]; srp=[x for x in self.repository.list_srp_records(well_id) if not x.get("archived_at")]; links=self.repository.list_measurement_links(well_id=well_id)
        measurements={x["measurement_id"]:x for x in self.repository.query_measurements(well_id,limit=10000)}
        cycle_links={c["cycle_id"]:[x for x in links if x["entity_type"]=="css_cycle" and x["entity_id"]==c["cycle_id"]] for c in cycles}
        def linked_valid(cycle_id: str, relations: set[str], variable: str) -> bool:
            for link in cycle_links.get(cycle_id,[]):
                measurement=measurements.get(link["measurement_id"])
                if link["relation"] not in relations or measurement is None or measurement["variable"]!=variable or measurement["quality_status"]!="VALID": continue
                if variable=="temperature_c":
                    context=measurement.get("provenance",{}).get("source_metadata",{})
                    if context.get("measurement_context")!="RESERVOIR_TEMPERATURE" or not (context.get("sensor_reference") or isinstance(context.get("sensor_depth_m"),(int,float))): continue
                return True
            return False
        css_ready=[c for c in cycles if c["status"]=="COMPLETE" and c["quality_status"]=="VALID" and c["completeness"]["missing_operational_inputs"]==[]
                   and all(c.get("quantities",{}).get(name,{}).get("quality_status","VALID")=="VALID" for name in ("injection_mass_tons","injection_pressure_bar","injection_temperature_c"))
                   and linked_valid(c["cycle_id"],{"POST_SOAK_TEMPERATURE","TEMPERATURE_TARGET"},"temperature_c")
                   and linked_valid(c["cycle_id"],{"PRODUCTION_OUTCOME","OIL_RATE_OUTCOME"},"oil_rate_bpd")]
        srp_config=[x for x in srp if x["record_type"]=="CONFIGURATION" and x["quality_status"]=="VALID" and all(q["quality_status"]=="VALID" for q in x["parameters"].values())]
        srp_observations=[x for x in srp if x["record_type"]=="OPERATING_OBSERVATION" and x["quality_status"]=="VALID" and all(q["quality_status"]=="VALID" for q in x["parameters"].values())]
        def configuration_applies(configuration, observation):
            if not configuration.get("valid_from") and not configuration.get("valid_to"):
                return configuration.get("valid_at")==observation.get("valid_at")
            return (not configuration.get("valid_from") or configuration["valid_from"]<=observation["valid_at"]) and (not configuration.get("valid_to") or configuration["valid_to"]>=observation["valid_at"])
        matched_srp_observations=[x for x in srp_observations if any(configuration_applies(c,x) for c in srp_config)]
        dynamometer=any(x.get("observations") and any(o.get("type")=="DYNAMOMETER_CARD" and o.get("quality_status","VALID")=="VALID" for o in x["observations"]) for x in srp_observations)
        css_blockers=[]
        if not cycles: css_blockers.append("No CSS cycle records")
        if any(c["status"]!="COMPLETE" for c in cycles): css_blockers.append("One or more cycles have incomplete injection/soak/production chronology")
        if not any(all(c.get("quantities",{}).get(name) and c["quantities"][name].get("quality_status","VALID")=="VALID" for name in ("injection_mass_tons","injection_pressure_bar","injection_temperature_c")) for c in cycles if c["status"]=="COMPLETE" and c["quality_status"]=="VALID"): css_blockers.append("No complete valid cycle has mass, injection pressure, and injection temperature")
        if not any(linked_valid(c["cycle_id"],{"POST_SOAK_TEMPERATURE","TEMPERATURE_TARGET"},"temperature_c") for c in cycles): css_blockers.append("No VALID post-soak reservoir temperature with sensor reference is linked to its CSS cycle")
        if not any(linked_valid(c["cycle_id"],{"PRODUCTION_OUTCOME","OIL_RATE_OUTCOME"},"oil_rate_bpd") for c in cycles): css_blockers.append("No VALID production outcome is linked to its CSS cycle")
        css_status="DATA_LINKAGE_READY_FOR_DOMAIN_REVIEW" if not css_blockers else "BLOCKED"
        srp_blockers=[]
        if not srp_config: srp_blockers.append("No valid time-stamped SRP configuration records")
        if not srp_observations: srp_blockers.append("No valid SRP operating observations")
        if srp_observations and not matched_srp_observations: srp_blockers.append("No operating observation falls within a time-valid SRP configuration")
        if not any("stroke_length_m" in x["parameters"] and "spm" in x["parameters"] for x in matched_srp_observations): srp_blockers.append("No paired stroke and stroke-rate observation under a valid configuration")
        if not any("oil_rate_bpd" in x["parameters"] for x in matched_srp_observations): srp_blockers.append("No production outcome in time-matched SRP observations")
        if not dynamometer: srp_blockers.append("No dynamometer/load-card data; load-dependent parameter assessment remains blocked")
        srp_status="DATA_LINKAGE_READY_FOR_DOMAIN_REVIEW" if not srp_blockers else "BLOCKED"
        joint_cycles={c["cycle_id"] for c in css_ready}; joint_records=[x for x in matched_srp_observations if x.get("metadata",{}).get("cycle_id") in joint_cycles]
        distinct_joint_cycles={x.get("metadata",{}).get("cycle_id") for x in joint_records}
        joint_blockers=[]
        if not joint_cycles: joint_blockers.append("No complete, measured CSS cycle with linked outcome")
        if not joint_records: joint_blockers.append("No SRP observation explicitly linked to a CSS cycle")
        css_parameter_names=("native_temp_c","steam_temp_c","steam_quality","latent_heat_kj_kg","water_cp_kj_kg_k","formation_thickness_m","porosity","rock_density_kg_m3","rock_cp_kj_kg_k","conduction_decay_rate")
        css_parameter_eligibility={name:{"classification":"INSUFFICIENT_DATA","reason":"No CSS sensitivity/calibration adapter is implemented; cycle-linked data readiness does not establish parameter identifiability."} for name in css_parameter_names}
        srp_parameter_names=("pump_depth_m","plunger_diameter_mm","rod_weight_air_n","tubing_id_mm","rod_outer_diameter_mm","fluid_density_kg_m3","steel_density_kg_m3")
        srp_parameter_eligibility={name:{"classification":"NOT_IDENTIFIABLE","reason":"The current SRP fit adapter is absent and oil-rate-only outputs confound this parameter with fluid, fillage, and load effects."} for name in srp_parameter_names}
        css_variation={name:{"min":min(vals) if vals else None,"max":max(vals) if vals else None,"unique_values":len(set(vals))} for name,vals in {
            "injection_mass_tons":[c["quantities"]["injection_mass_tons"]["value"] for c in css_ready],
            "injection_pressure_bar":[c["quantities"]["injection_pressure_bar"]["value"] for c in css_ready],
            "injection_temperature_c":[c["quantities"]["injection_temperature_c"]["value"] for c in css_ready],
            "soak_duration_days":[(datetime.fromisoformat(c["soak_end"])-datetime.fromisoformat(c["soak_start"])).total_seconds()/86400 for c in css_ready]}.items()}
        return {"well_id":well_id,"css":{"status":css_status,"eligible_cycle_count":len(css_ready),"sample_size_assessment":"DOMAIN_DEFINED_THRESHOLD_NOT_SET","input_variation":css_variation,"parameter_eligibility":css_parameter_eligibility,"blockers":css_blockers},
                "srp":{"status":srp_status,"configuration_record_count":len(srp_config),"observation_count":len(srp_observations),"configuration_matched_observation_count":len(matched_srp_observations),"dynamometer_available":dynamometer,"sample_size_assessment":"DOMAIN_DEFINED_THRESHOLD_NOT_SET","parameter_eligibility":srp_parameter_eligibility,"blockers":srp_blockers},
                "css_srp_coupled":{"status":"BLOCKED" if joint_blockers else "JOINT_DATA_AVAILABLE_FOR_IDENTIFIABILITY_REVIEW","joint_observation_count":len(joint_records),"distinct_joint_cycle_count":len(distinct_joint_cycles),"sample_size_assessment":"DOMAIN_DEFINED_THRESHOLD_NOT_SET","calibration_supported":False,"parameter_eligibility":{"interaction_effect":{"classification":"INSUFFICIENT_DATA","reason":"No validated coupled CSS-SRP model or identifiability method exists."}},"blockers":joint_blockers or ["No coupled CSS-SRP calibration adapter exists; joint observations only permit future identifiability research."]},
                "operating_regime":{"status":"EXPLICIT_LABELS_ONLY","available_labels":sorted({label for c in cycles for label in c.get("metadata",{}).get("operating_regime_labels",[])})},
                "provenance":{"measurement_link_count":len(links),"event_count":len(events),"cycle_count":len(cycles),"srp_record_count":len(srp)}}

    def build_dataset(self, well_id: str, dataset_type: str, start_at: datetime, end_at: datetime, cycle_id: str | None = None, calibration_fraction: float = 0.8, regime_label: str | None = None, temporal_gap_hours: float = 0) -> dict[str, Any]:
        self._known_well(well_id)
        start=_time(start_at,"start_at"); end=_time(end_at,"end_at")
        if end <= start: raise ValueError("end_at must be after start_at")
        if dataset_type not in {"css_cycle","srp","css_srp_joint","event_aligned","regime_aware"}: raise ValueError("unsupported dataset_type")
        if not 0.5 <= calibration_fraction < 1: raise ValueError("calibration_fraction must be at least 0.5 and less than 1")
        if not 0 <= temporal_gap_hours <= 8760: raise ValueError("temporal_gap_hours must be between 0 and 8760")
        cycles=[x for x in self.repository.list_css_cycles(well_id) if not x.get("archived_at") and start <= (x.get("injection_start") or "") <= end]
        if cycle_id:
            cycles=[x for x in cycles if x["cycle_id"]==cycle_id]
            if not cycles: raise ValueError("cycle_id does not identify a CSS cycle for this well and period")
        srp=[x for x in self.repository.list_srp_records(well_id,start_at=start,end_at=end) if not x.get("archived_at")]
        events=[x for x in self.repository.list_operational_events(well_id,start_at=start,end_at=end) if not x.get("archived_at")]
        if dataset_type in {"css_cycle","event_aligned"}: srp=[]
        if dataset_type=="srp": cycles=[]; events=[]
        if dataset_type=="event_aligned": cycles=[]
        if dataset_type=="regime_aware":
            cycles=[x for x in cycles if x.get("metadata",{}).get("operating_regime_labels")]
            srp=[x for x in srp if x.get("metadata",{}).get("operating_regime_labels")]
            events=[x for x in events if x.get("metadata",{}).get("operating_regime_labels")]
            if regime_label:
                cycles=[x for x in cycles if regime_label in x.get("metadata",{}).get("operating_regime_labels",[])]
                srp=[x for x in srp if regime_label in x.get("metadata",{}).get("operating_regime_labels",[])]
                events=[x for x in events if regime_label in x.get("metadata",{}).get("operating_regime_labels",[])]
        links=self.repository.list_measurement_links(well_id=well_id)
        measurement_ids={x["measurement_id"] for x in links if (x["entity_type"]=="css_cycle" and x["entity_id"] in {c["cycle_id"] for c in cycles}) or (x["entity_type"]=="srp_record" and x["entity_id"] in {r["record_id"] for r in srp}) or (x["entity_type"]=="operational_event")}
        all_measurements=self.repository.query_measurements(well_id,start_at=start,end_at=end,limit=10000)
        measurement_map={x["measurement_id"]:x for x in all_measurements}
        rows=[]; excluded=[]
        for cycle in cycles:
            linked=[x for x in links if x["entity_type"]=="css_cycle" and x["entity_id"]==cycle["cycle_id"]]
            linked_measurements=[{**measurement_map[x["measurement_id"]],"relation":x["relation"]} for x in linked if x["measurement_id"] in measurement_map]
            rows.append({"group_type":"css_cycle","group_id":cycle["cycle_id"],"cycle_number":cycle["cycle_number"],"operating_regime_labels":cycle.get("metadata",{}).get("operating_regime_labels",[]),"cycle":cycle,"measurements":linked_measurements})
            if not linked: excluded.append({"record_id":cycle["cycle_id"],"reason":"no_cycle_measurements_linked"})
        for record in srp:
            linked=[x for x in links if x["entity_type"]=="srp_record" and x["entity_id"]==record["record_id"]]
            linked_measurements=[{**measurement_map[x["measurement_id"]],"relation":x["relation"]} for x in linked if x["measurement_id"] in measurement_map]
            rows.append({"group_type":"srp_record","group_id":record["record_id"],"record_type":record["record_type"],"record":record,"measurements":linked_measurements})
            if not linked: excluded.append({"record_id":record["record_id"],"reason":"no_measurements_linked"})
        if dataset_type in {"event_aligned","regime_aware"}:
            for event in events:
                linked=[x for x in links if x["entity_type"]=="operational_event" and x["entity_id"]==event["event_id"]]
                linked_measurements=[{**measurement_map[x["measurement_id"]],"relation":x["relation"]} for x in linked if x["measurement_id"] in measurement_map]
                rows.append({"group_type":"operational_event","group_id":event["event_id"],"event":event,"measurements":linked_measurements})
                if not linked_measurements: excluded.append({"record_id":event["event_id"],"reason":"no_in_period_event_measurements_linked"})
        if dataset_type=="css_srp_joint":
            srp_by_cycle={}
            for record in srp:
                linked_cycle=record.get("metadata",{}).get("cycle_id")
                if linked_cycle: srp_by_cycle.setdefault(linked_cycle,[]).append(record)
            joint_rows=[]
            for cycle in cycles:
                related=srp_by_cycle.get(cycle["cycle_id"],[])
                if not related: excluded.append({"record_id":cycle["cycle_id"],"reason":"no_explicitly_linked_srp_record_for_css_cycle"}); continue
                cycle_row=next((row for row in rows if row["group_id"]==cycle["cycle_id"]),None)
                if cycle_row is None: continue
                has_temperature=any(m["variable"]=="temperature_c" and m["quality_status"]=="VALID" and m["relation"] in {"POST_SOAK_TEMPERATURE","TEMPERATURE_TARGET"}
                    and m.get("provenance",{}).get("source_metadata",{}).get("measurement_context")=="RESERVOIR_TEMPERATURE"
                    and (m.get("provenance",{}).get("source_metadata",{}).get("sensor_reference") or isinstance(m.get("provenance",{}).get("source_metadata",{}).get("sensor_depth_m"),(int,float))) for m in cycle_row["measurements"])
                has_cycle_oil=any(m["variable"]=="oil_rate_bpd" and m["quality_status"]=="VALID" and m["relation"] in {"PRODUCTION_OUTCOME","OIL_RATE_OUTCOME"} for m in cycle_row["measurements"])
                if cycle.get("status")!="COMPLETE" or cycle.get("quality_status")!="VALID" or not has_temperature or not has_cycle_oil:
                    excluded.append({"record_id":cycle["cycle_id"],"reason":"joint_cycle_requires_complete_quality_and_linked_temperature_and_production_outcomes"}); continue
                for srp_record in related:
                    srp_row=next((row for row in rows if row["group_id"]==srp_record["record_id"]),None)
                    if srp_row is None: continue
                    params=srp_record.get("parameters",{})
                    has_srp_oil=any(m["variable"]=="oil_rate_bpd" and m["quality_status"]=="VALID" and m["relation"] in {"PRODUCTION_OUTCOME","OIL_RATE_OUTCOME"} for m in srp_row["measurements"])
                    config_match=any(c["record_type"]=="CONFIGURATION" and c["quality_status"]=="VALID" and configuration_applies(c,srp_record) for c in srp)
                    if srp_record.get("record_type")!="OPERATING_OBSERVATION" or srp_record.get("quality_status")!="VALID" or not {"stroke_length_m","spm","oil_rate_bpd"}<=set(params) or not has_srp_oil or not config_match:
                        excluded.append({"record_id":srp_record["record_id"],"reason":"joint_srp_requires_time_matched_configuration_stroke_rate_and_linked_production_outcome"}); continue
                    joint_rows.append({"group_type":"css_srp_joint","group_id":cycle["cycle_id"],"cycle_id":cycle["cycle_id"],"cycle":cycle,"srp_record":srp_record,
                        "measurements":cycle_row["measurements"]+srp_row["measurements"],"operating_regime_labels":cycle.get("metadata",{}).get("operating_regime_labels",[])})
            rows=joint_rows
        if dataset_type=="regime_aware":
            labeled=[]
            for row in rows:
                labels=row.get("operating_regime_labels") or row.get("cycle",{}).get("metadata",{}).get("operating_regime_labels") or row.get("record",{}).get("metadata",{}).get("operating_regime_labels")
                row["operating_regime_labels"]=labels or []
                if labels: labeled.append(row)
                else: excluded.append({"record_id":row["group_id"],"reason":"operating_regime_not_explicitly_labeled"})
            rows=labeled
        def group_bounds(row):
            if row.get("cycle"):
                cycle=row["cycle"]; return cycle.get("injection_start") or cycle.get("created_at"),cycle.get("post_soak_observation_end") or cycle.get("production_restart") or cycle.get("injection_end") or cycle.get("injection_start") or cycle.get("created_at")
            record=row.get("record") or row.get("event") or {}
            return record.get("valid_at") or record.get("occurred_at") or record.get("created_at"),record.get("valid_to") or record.get("ended_at") or record.get("valid_at") or record.get("occurred_at") or record.get("created_at")
        bounds={}
        for row in rows:
            start_value,end_value=group_bounds(row); key=row["group_id"]
            if start_value is None: continue
            current=bounds.get(key)
            bounds[key]=(min(current[0],start_value),max(current[1],end_value or start_value)) if current else (start_value,end_value or start_value)
        ordered_groups=sorted(bounds,key=lambda key:(bounds[key][0],key))
        split_index=max(1,min(len(ordered_groups)-1,int(len(ordered_groups)*calibration_fraction))) if len(ordered_groups)>=2 else len(ordered_groups)
        calibration_groups=set(ordered_groups[:split_index]); validation_candidates=ordered_groups[split_index:]
        calibration_end=max((bounds[key][1] for key in calibration_groups),default=None)
        gap_start=(datetime.fromisoformat(calibration_end.replace("Z","+00:00")) if calibration_end else None)
        validation_groups=set()
        for key in validation_candidates:
            group_start=datetime.fromisoformat(bounds[key][0].replace("Z","+00:00"))
            if gap_start is not None and (group_start-gap_start).total_seconds()<temporal_gap_hours*3600:
                excluded.append({"record_id":key,"reason":"temporal_gap_or_group_overlap"})
            else: validation_groups.add(key)
        for row in rows:
            row["chronological_split"]="CALIBRATION" if row["group_id"] in calibration_groups else "VALIDATION_UNTOUCHED" if row["group_id"] in validation_groups else "EXCLUDED_TEMPORAL_GAP_OR_INSUFFICIENT_GROUPS"
        payload={"well_id":well_id,"model_id":f"operational_{dataset_type}","dataset_type":dataset_type,"period":{"start_at":start,"end_at":end},
            "cycle_id":cycle_id,"split_method":"chronological_grouped_no_random_split" if len(ordered_groups)>=2 and validation_groups else "chronological_order_insufficient_groups_or_gap_for_split","calibration_fraction":calibration_fraction,"temporal_gap_hours":temporal_gap_hours,"group_count":len(ordered_groups),"calibration_group_count":len(calibration_groups),"validation_group_count":len(validation_groups),"observations":rows,"observation_count":len(rows),
            "excluded_records":excluded,"linked_measurement_ids":sorted({m["measurement_id"] for row in rows for m in row["measurements"]}),
            "operating_regime":{"status":"EXPLICIT_LABELS_ONLY","requested_label":regime_label,"labels":sorted({label for row in rows for label in row.get("operating_regime_labels",[])})},
            "operational_event_ids":sorted({x["entity_id"] for x in links if x["entity_type"]=="operational_event" and x["measurement_id"] in measurement_ids}),
            "calibration_support":"READINESS_DATASET_ONLY_NO_ADAPTER"}
        payload["fingerprint"]=_fingerprint(payload)
        return self.repository.save_calibration_dataset(payload)

    def import_records(self, record_type: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        if record_type not in {"css_cycle","event","srp_record"}: raise ValueError("record_type must be css_cycle, event, or srp_record")
        accepted=[]; rejected=[]; duplicates=0
        for number,row in enumerate(rows,start=1):
            try:
                if not isinstance(row,dict): raise ValueError("row must be an object")
                result=(self.create_css_cycle(row) if record_type=="css_cycle" else self.create_event(row) if record_type=="event" else self.create_srp_record(row))
                accepted.append({"row":str(number),"record_id":result.get("cycle_id",result.get("event_id",result.get("record_id")))})
            except Exception as exc:
                reason=str(exc)
                if "unique constraint" in reason.lower() or "duplicate key" in reason.lower(): duplicates += 1
                else: rejected.append({"row":str(number),"reason":reason[:300]})
        return {"schema_version":"1.0","record_type":record_type,"accepted":len(accepted),"duplicates":duplicates,"rejected":rejected,"records":accepted,"persistence":"accepted records are committed per row; a failed row does not roll back prior accepted records"}
