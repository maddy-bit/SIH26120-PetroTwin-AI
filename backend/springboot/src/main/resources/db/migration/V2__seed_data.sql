-- PETRO-TWIN AI: V2 Seed Data Migration

-- Roles
INSERT INTO roles (role_id, description) VALUES
('ADMIN', 'Full Asset Administrator'),
('ENGINEER', 'Petroleum / Reservoir / Production Engineer'),
('OPERATOR', 'Field Production Operator'),
('VIEWER', 'Read-Only Asset Observer')
ON CONFLICT (role_id) DO NOTHING;

-- Demo Users (Passwords hashed with BCrypt, default demo password 'password123')
INSERT INTO users (user_id, username, email, password_hash, role_id, is_active) VALUES
('USR-001', 'admin', 'admin@oilindia.in', '$2a$10$wTkyrW6zN6d9sM2aQ8qDceG7N1G0pA2Xm4zJ8h9dK6qE0wA2Xm4zJ', 'ADMIN', TRUE),
('USR-002', 'anmol_engineer', 'engineer@oilindia.in', '$2a$10$wTkyrW6zN6d9sM2aQ8qDceG7N1G0pA2Xm4zJ8h9dK6qE0wA2Xm4zJ', 'ENGINEER', TRUE),
('USR-003', 'field_operator', 'operator@oilindia.in', '$2a$10$wTkyrW6zN6d9sM2aQ8qDceG7N1G0pA2Xm4zJ8h9dK6qE0wA2Xm4zJ', 'OPERATOR', TRUE)
ON CONFLICT (user_id) DO NOTHING;

-- Reservoir
INSERT INTO reservoirs (reservoir_id, name, basin, formation, initial_temperature_c, initial_pressure_bar, api_gravity, native_viscosity_cp) VALUES
('RES-BAGHEWALA-01', 'Baghewala Heavy Oil Reservoir', 'Bikaner-Nagaur Basin', 'Jodhpur Sandstone', 47.0, 55.0, 18.2, 4200.0)
ON CONFLICT (reservoir_id) DO NOTHING;

-- Wells
INSERT INTO wells (well_id, well_name, reservoir_id, depth_m, pump_depth_m, tubing_id_mm, casing_id_mm, active_cycle_number, status, data_source_mode) VALUES
('BW-DEMO-001', 'Baghewala Demo Well 001 (Thermal Decay Stage)', 'RES-BAGHEWALA-01', 950.0, 900.0, 62.0, 152.4, 3, 'ACTIVE_PRODUCTION', 'SIMULATION'),
('BW-DEMO-002', 'Baghewala Demo Well 002 (Peak Thermal Stage)', 'RES-BAGHEWALA-01', 960.0, 910.0, 62.0, 152.4, 4, 'ACTIVE_PRODUCTION', 'SIMULATION'),
('BW-DEMO-003', 'Baghewala Demo Well 003 (Critical Cooling Warning)', 'RES-BAGHEWALA-01', 940.0, 890.0, 62.0, 152.4, 2, 'ACTIVE_PRODUCTION', 'SIMULATION')
ON CONFLICT (well_id) DO NOTHING;

-- Well Completion
INSERT INTO well_completion (completion_id, well_id, tubing_od_in, casing_od_in, perforation_top_m, perforation_bottom_m, sand_control_type) VALUES
('COMP-001', 'BW-DEMO-001', 2.875, 7.0, 930.0, 948.0, 'Wire-Wrapped Screen'),
('COMP-002', 'BW-DEMO-002', 2.875, 7.0, 935.0, 955.0, 'Slotted Liner'),
('COMP-003', 'BW-DEMO-003', 2.875, 7.0, 920.0, 938.0, 'Gravel Pack')
ON CONFLICT (completion_id) DO NOTHING;

-- Model Registry
INSERT INTO model_versions (model_version_id, model_name, version_string, training_dataset, mae, rmse, status) VALUES
('MDL-PROD-V1', 'hybrid_production_forecaster', 'v1.4.0', 'Tier-A Volve + Tier-B Baghewala Literature', 4.20, 6.10, 'ACTIVE'),
('MDL-FAIL-V1', 'failure_intelligence_risk', 'v1.4.0', 'PetroBench + Literature Dyno Cards', 0.05, 0.08, 'ACTIVE'),
('MDL-ANOM-V1', 'telemetry_anomaly_detector', 'v1.4.0', 'Baghewala Synthetic Normal Telemetry', 0.02, 0.04, 'ACTIVE')
ON CONFLICT (model_version_id) DO NOTHING;
