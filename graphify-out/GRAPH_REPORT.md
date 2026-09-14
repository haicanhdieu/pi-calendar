# Graph Report - pi-calendar  (2026-09-14)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 3064 nodes · 7008 edges · 130 communities (103 shown, 18 thin omitted)
- Extraction: 98% EXTRACTED · 2% INFERRED · 0% AMBIGUOUS · INFERRED: 127 edges (avg confidence: 0.89)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `e8de82d2`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- Community 0
- Community 1
- Community 2
- Community 3
- Community 4
- Community 5
- Community 6
- Community 7
- Community 8
- Community 9
- Community 10
- Community 11
- Community 12
- Community 13
- Community 14
- Community 15
- Community 16
- Community 17
- Community 18
- Community 19
- Community 20
- Community 21
- Community 22
- Community 23
- Community 24
- Community 25
- Community 26
- Community 27
- Community 28
- Community 29
- Community 30
- Community 31
- Community 32
- Community 33
- Community 34
- Community 35
- Community 36
- Community 37
- Community 38
- Community 39
- Community 40
- Community 41
- Community 42
- Community 43
- Community 44
- Community 45
- Community 46
- Community 47
- Community 48
- Community 49
- Community 50
- Community 51
- Community 52
- Community 53
- Community 54
- Community 55
- Community 56
- Community 57
- Community 58
- Community 59
- Community 60
- Community 61
- Community 62
- Community 63
- Community 64
- Community 65
- Community 66
- Community 67
- Community 68
- Community 69
- Community 70
- Community 71
- Community 72
- Community 73
- Community 74
- Community 75
- Community 76
- Community 77
- Community 78
- Community 79
- Community 80
- Community 81
- Community 82
- Community 83
- Community 84
- Community 85
- Community 86
- Community 87
- Community 88
- Community 89
- Community 90
- Community 91
- Community 92
- Community 93
- Community 94
- Community 95
- Community 96
- Community 97
- Community 98
- Community 99
- Community 100
- Community 101
- Community 102
- Community 103
- Community 104
- Community 105
- Community 106
- Community 107
- Community 108
- Community 109
- Community 110
- Community 111
- Community 112
- Community 113
- Community 114
- Community 115
- Community 116
- Community 117
- Community 118
- Community 119
- Community 122

## God Nodes (most connected - your core abstractions)
1. `NetworkCoordinator` - 96 edges
2. `Mailbox` - 67 edges
3. `_run()` - 66 edges
4. `_run()` - 66 edges
5. `FakeDisplayPort` - 63 edges
6. `DateTime` - 57 edges
7. `SyncCommand` - 54 edges
8. `_json()` - 53 edges
9. `_json()` - 53 edges
10. `FakeTicks` - 50 edges

## Surprising Connections (you probably didn't know these)
- `test_app_and_ticks_import_under_cpython()` --uses--> `App`  [INFERRED]
  tests/test_app_loop.py → src/app.py
- `main()` --uses--> `ILI9341`  [INFERRED]
  main.py → src/device/display/ili9341.py
- `main()` --uses--> `Pin`  [INFERRED]
  main.py → tools/hostsim/stubs/machine.py
- `main()` --uses--> `SPI`  [INFERRED]
  main.py → tools/hostsim/stubs/machine.py
- `test_saturation_preserves_prior_result()` --uses--> `MailboxSaturationError`  [INFERRED]
  tests/test_app_sync.py → src/device/network/mailbox.py

## Import Cycles
- None detected.

## Communities (130 total, 18 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.08
Nodes (80): _json(), _load(), _module(), parametrize, skipif, Import the script as a module, for the few properties that cannot be triggered…, Parse the JSON-only stdout contract, surfacing a crash instead of hiding it…, _run() (+72 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (80): _json(), _load(), _module(), parametrize, skipif, Import the script as a module, for the few properties that cannot be triggered…, Parse the JSON-only stdout contract, surfacing a crash instead of hiding it…, _run() (+72 more)

### Community 2 - "Community 2"
Cohesion: 0.07
Nodes (63): AppState, Mutable product state owned exclusively by App., _enter_settings_via_gear(), FakeClockPort, FakeRebootPort, FakeTicks, FakeTouchPort, _imported_roots() (+55 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (57): ConfigError, _detect_keyed_merge_field(), load_central_config(), load_customization(), load_toml(), _merge_arrays(), merge_layers(), Any (+49 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (56): _atomic_write(), build_parser(), cmd_detect_epic(), cmd_update(), _comment_counts(), _dump_bytes(), _emit(), _emit_error() (+48 more)

### Community 5 - "Community 5"
Cohesion: 0.07
Nodes (56): _atomic_write(), build_parser(), cmd_detect_epic(), cmd_update(), _comment_counts(), _dump_bytes(), _emit(), _emit_error() (+48 more)

### Community 6 - "Community 6"
Cohesion: 0.10
Nodes (55): _accented_repo(), _assert_accented_path(), _binary_repo(), _fake_git(), _git(), _git_env(), _git_unchecked(), _json() (+47 more)

### Community 7 - "Community 7"
Cohesion: 0.10
Nodes (55): _accented_repo(), _assert_accented_path(), _binary_repo(), _fake_git(), _git(), _git_env(), _git_unchecked(), _json() (+47 more)

### Community 8 - "Community 8"
Cohesion: 0.10
Nodes (44): Glanceable time state for renderers and view gating., TimeSnapshot, ClockView, Force full redraw on next render (view entry / badge base restore)., Centered 24-hour Clock renderer over DisplayPort only., Owns previous status-overlay visibility for Clock and Calendar base views. On a…, UiCompositor, FakeDisplayPort (+36 more)

### Community 9 - "Community 9"
Cohesion: 0.08
Nodes (37): build_month_grid(), days_in_month(), _next_month(), _prev_month(), Pure Gregorian month-grid generation (Monday=0, no hardware imports)., Gregorian month length (%4 / %100 / %400 leap rule)., Civil weekday from (year, month, day). Returns Monday=0 … Sunday=6. Does not…, Build a Monday-first MonthGrid for ``local_year``/``local_month``. Adjacent-… (+29 more)

### Community 10 - "Community 10"
Cohesion: 0.08
Nodes (32): Mailbox, Accept a SyncCommand only while idle, command slot empty, and result slot empty…, Worker atomically takes the pending command, or None if empty. On take, returns…, App consumes the pending result, or None if empty., Clear both slots, restore idle, and bump epoch (orphan publishes)., One bounded sync request from App to the network worker., Separate capacity-one command and result slots plus an idle flag. Enqueue only…, SyncCommand (+24 more)

### Community 11 - "Community 11"
Cohesion: 0.08
Nodes (32): FakeTicks, FakeWlan, _configured_store(), _coordinator(), _FakeKdfJob, _online_store_coordinator(), Host tests for store-credential station recovery (story 1.3)., Persist-gated online emit clears the counter (setup join path). (+24 more)

### Community 12 - "Community 12"
Cohesion: 0.11
Nodes (42): load(), out_json(), The template's STATUS DEFINITIONS block and the script's HEADER_COMMENT are two…, run_generate(), run_status(), run_validate(), test_action_items_carried_verbatim(), test_argument_errors_emit_json() (+34 more)

### Community 13 - "Community 13"
Cohesion: 0.11
Nodes (42): load(), out_json(), The template's STATUS DEFINITIONS block and the script's HEADER_COMMENT are two…, run_generate(), run_status(), run_validate(), test_action_items_carried_verbatim(), test_argument_errors_emit_json() (+34 more)

### Community 14 - "Community 14"
Cohesion: 0.09
Nodes (35): cookie_header_value(), Return the value of ``name`` from a raw ``Cookie`` header, or ``None``. Parses…, response_bad_request(), response_busy(), _lookup_session(), Allowlisted setup/config HTTP routing (pure)., Outcome of routing one completed request., Volatile pending setup join (secrets held only until terminal outcome). (+27 more)

### Community 15 - "Community 15"
Cohesion: 0.14
Nodes (33): CalendarView, _format_month_label(), _month_name(), Current-month Calendar view renderer (FR5 / UX calendar chrome)., MonthGrid Calendar renderer over DisplayPort only (no badge draw)., Force full redraw on next render (view entry / compositor restore)., Draw the Calendar chrome from an already-built MonthGrid. ``snapshot`` is…, _calendar_cell_geometry() (+25 more)

### Community 16 - "Community 16"
Cohesion: 0.14
Nodes (29): _http_get(), _http_login_post(), _http_password_change_post(), _login_for_cookie(), _online_coordinator(), _pump(), Host tests for Config login, session gate, and cooperative KDF auth., Regression: a MemoryError/Exception while lazily importing the station web/page… (+21 more)

### Community 17 - "Community 17"
Cohesion: 0.06
Nodes (7): _cp1252_stream(), extra(), lib(), fixture, A text stream that behaves like a Windows console: cp1252, strict., test_extra_technique_prints_when_stdout_encoding_is_cp1252(), test_missing_technique_name_reports_when_stderr_encoding_is_cp1252()

### Community 18 - "Community 18"
Cohesion: 0.06
Nodes (7): _cp1252_stream(), extra(), lib(), fixture, A text stream that behaves like a Windows console: cp1252, strict., test_extra_technique_prints_when_stdout_encoding_is_cp1252(), test_missing_technique_name_reports_when_stderr_encoding_is_cp1252()

### Community 19 - "Community 19"
Cohesion: 0.08
Nodes (22): main(), Non-secret hardware and product defaults (AD-9)., Pack an RGB888 triple into a high-byte-first RGB565 integer., rgb888_to_rgb565(), initialize_display(), Host-testable display boot boundary for the composition root., Initialize the panel, render its checkpoint, and wait briefly., color565() (+14 more)

### Community 20 - "Community 20"
Cohesion: 0.10
Nodes (25): Terminal worker outcome for one SyncCommand., SyncResult, FakeClockPort, FakeLock, FakeTicks, _imported_roots(), _make_sync_app(), Path (+17 more)

### Community 21 - "Community 21"
Cohesion: 0.10
Nodes (31): html_escape(), parse_form_urlencoded(), _percent_decode(), Bounded incremental HTTP/1.0–1.1 request parsing (pure; no sockets)., Escape text for safe inclusion in HTML text/attribute contexts., Parse ``application/x-www-form-urlencoded`` body to a string dict. Duplicate…, Small, self-contained server-rendered setup page., Render scan results and setup state without browser-side requests. (+23 more)

### Community 22 - "Community 22"
Cohesion: 0.09
Nodes (23): decode_session_id(), encode_session_id(), Bounded in-memory session table (AD-5). Opaque 16-byte IDs encoded as unpadded…, Drop entries whose idle deadline has passed (wrap-safe)., Create a session after expiry sweep. Returns the encoded id, or ``None`` when…, Return the matching live entry, or ``None`` if absent/expired/malformed., Renew idle deadline for a live session; return True on success., After expiry sweep, retain only the acting session and renew it. Returns True… (+15 more)

### Community 23 - "Community 23"
Cohesion: 0.10
Nodes (35): activeRules(), blank(), commentIndex(), crypto, DEFAULT_CONFIG, DEFERRED, expandBraces(), EXTENSION_KIND (+27 more)

### Community 24 - "Community 24"
Cohesion: 0.10
Nodes (35): activeRules(), blank(), commentIndex(), crypto, DEFAULT_CONFIG, DEFERRED, expandBraces(), EXTENSION_KIND (+27 more)

### Community 25 - "Community 25"
Cohesion: 0.10
Nodes (34): _card(), categories(), category_style(), filter_cats(), find(), fmt_categories(), fmt_list(), fmt_show() (+26 more)

### Community 26 - "Community 26"
Cohesion: 0.10
Nodes (34): _card(), categories(), category_style(), filter_cats(), find(), fmt_categories(), fmt_list(), fmt_show() (+26 more)

### Community 27 - "Community 27"
Cohesion: 0.10
Nodes (13): App, Enter Clock as the active view and arm tick deadlines., Soft-fail path for expected sync/credential problems. Marks trust unsynced,…, One non-blocking loop iteration (AD-12 event order). When ``now_ticks`` is…, Read the optional touch port once and commit its surface decision., Draw Press Flash, dwell, then invoke the injected reboot port once., Use the short cadence only while the Bar reveal is in progress., Immutable-ish retained network-status payload for Settings. (+5 more)

### Community 28 - "Community 28"
Cohesion: 0.13
Nodes (26): add_months(), appendix_rows(), cell_html(), cmd_citations(), cmd_escape_sources(), cmd_slug(), cmd_staleness(), cmd_tally() (+18 more)

### Community 29 - "Community 29"
Cohesion: 0.13
Nodes (26): add_months(), appendix_rows(), cell_html(), cmd_citations(), cmd_escape_sources(), cmd_slug(), cmd_staleness(), cmd_tally() (+18 more)

### Community 30 - "Community 30"
Cohesion: 0.09
Nodes (22): Ili9341DisplayPort, DisplayPort adapter over the existing ILI9341 driver (device layer only)., Maps half-open DisplayPort rects/text to ILI9341 inclusive windows. Owns no…, clip_half_open(), draw_spaced_text(), measure_font_text(), measure_spaced_font_text(), Neutral geometry helpers shared by UI and device display layers. (+14 more)

### Community 31 - "Community 31"
Cohesion: 0.13
Nodes (11): NetworkCoordinator, Create the bounded web surface only when the active mode serves it., Record a secret-free web failure once and schedule a later retry., Re-arm reporting once a previously failed phase succeeds., Optional device-only heap evidence; never changes serving behavior., Allocate config-auth session state only after reaching station work., Compact setup scan state: ``empty``, ``ok``, or ``failed``., Secret-free diagnostic name for the last failed scan. (+3 more)

### Community 32 - "Community 32"
Cohesion: 0.11
Nodes (29): login_page_html(), Minimal station-online login page., Minimal station-online settings page using native controls., settings_page_html(), http_response(), login_page_html(), HTTP response builders (pure). The three page-HTML builders…, Build a fixed HTTP/1.0 response bytes (Connection: close). (+21 more)

### Community 33 - "Community 33"
Cohesion: 0.14
Nodes (25): Cooperative, core-0 WLAN and NTP coordinator. Each :meth:`tick` performs at…, NetworkEvent, next_station_failure_count(), Network mode constants and typed NetworkEvent values. Pure module: no…, Golden SETUP_AP status event (SSID + gateway, no display calls)., Named SETUP_AP failure without crashing the coordinator., Station online/connecting status without App/TFT mutation., Increment consecutive terminal station failures (pure). (+17 more)

### Community 34 - "Community 34"
Cohesion: 0.12
Nodes (9): Drop every client connection but leave the listen socket bound., Drop a failed request without losing the setup candidate reply., Advance one bounded unit of HTTP work. Setup mode may return ``(\"connect\",…, Flush a terminal response to the held Connect/login client., Advance pending response writes without accepting new work., Release held Connect/login slot when the peer closes mid-work., Accept/read/write at most one bounded step per ``tick``., Whether a browser has reached this server (without allocating auth). (+1 more)

### Community 35 - "Community 35"
Cohesion: 0.10
Nodes (25): badge_rect(), bar_gear_item_rect(), bar_rect(), draw_bar(), draw_unsynced_badge(), point_in_rect(), Shared status-layer drawing helpers (AD-12 seed)., Draw the bounded Bar panel and its centered amber gear, draw-last only. (+17 more)

### Community 36 - "Community 36"
Cohesion: 0.09
Nodes (12): cats(), test_duplicate_ad_id_caught(), test_fenced_stack_heading_not_live(), test_fenced_stack_rows_not_parsed(), test_mermaid_braces_not_flagged(), test_no_frontmatter_body_still_scanned(), test_no_stack_section_ok(), test_placeholder_markers_caught() (+4 more)

### Community 37 - "Community 37"
Cohesion: 0.07
Nodes (9): The default room is installed agents only; pure customs stay in the pool., The wrapper knows the project root, so it must not let the resolver infer one…, TestAlias, TestBuildCollective, TestGroupDetail, TestGroups, TestInstalledCodesIsDefaultRoom, TestResolveMembers (+1 more)

### Community 38 - "Community 38"
Cohesion: 0.09
Nodes (12): cats(), test_duplicate_ad_id_caught(), test_fenced_stack_heading_not_live(), test_fenced_stack_rows_not_parsed(), test_mermaid_braces_not_flagged(), test_no_frontmatter_body_still_scanned(), test_no_stack_section_ok(), test_placeholder_markers_caught() (+4 more)

### Community 39 - "Community 39"
Cohesion: 0.07
Nodes (9): The default room is installed agents only; pure customs stay in the pool., The wrapper knows the project root, so it must not let the resolver infer one…, TestAlias, TestBuildCollective, TestGroupDetail, TestGroups, TestInstalledCodesIsDefaultRoom, TestResolveMembers (+1 more)

### Community 40 - "Community 40"
Cohesion: 0.26
Nodes (29): _allocate_lock(), _enqueue(), _is_clean(), _log(), _marker(), _mem_free(), Flashable AD-8 network mailbox proof harness (Story 1.4). Exercises…, Wait for idle + drain, or soft_reset, before the next scenario. (+21 more)

### Community 41 - "Community 41"
Cohesion: 0.17
Nodes (24): derive_admin_verifier(), Derive ``(salt_hex, verifier_hex)`` for an Admin password. ``salt`` may be 16…, Shared list: coordinator emit → App.step → retained status; sync gates., test_shared_events_composition_coordinator_to_app_overlay(), FakeFS, Host tests for SettingsStore AD-3 persistence and recovery., Minimal injectable filesystem for SettingsStore., _record_bytes() (+16 more)

### Community 42 - "Community 42"
Cohesion: 0.13
Nodes (21): make_settings_coordinator(), ntp_sync_enabled(), True only when not in SETUP_AP and credentials soft-check passed., Composition helper: NetworkCoordinator wired to SettingsStore + event sink., Secrets, FakeApWlan, FakeDefaultHttpSockets, Host tests for SETUP_AP boot ownership on NetworkCoordinator. (+13 more)

### Community 43 - "Community 43"
Cohesion: 0.18
Nodes (23): FakeSocketModule, make_coordinator(), ntp_payload(), Host proof for the tick-driven WLAN/NTP coordinator., ScanWlan, terminal(), test_cached_scan_is_reused_until_a_rescan_forces_a_refresh(), test_deadline_closes_pending_socket_and_publishes_once() (+15 more)

### Community 44 - "Community 44"
Cohesion: 0.09
Nodes (16): Bounded local HTTP setup surface (parse/route/pages are host-pure)., _json_string(), Forward-only, bounded HTTP response sources., Return and consume at most ``max_bytes`` encoded response bytes., A response made of immutable segments with one advancing cursor., Keep byte-response inspection helpers working on host tests., _response_chunk(), ResponseSource (+8 more)

### Community 45 - "Community 45"
Cohesion: 0.23
Nodes (20): _activate(), FakeTcpSocketModule, _http_connect(), _http_get(), _make(), _pump_until(), Host tests for setup candidate join/persist ordering on NetworkCoordinator., ScanWlan (+12 more)

### Community 46 - "Community 46"
Cohesion: 0.13
Nodes (24): lib(), fixture, rows(), run(), test_categories_counts_sorted(), test_cli_bad_extra_and_missing_file(), test_cli_categories(), test_cli_extra_inline_json() (+16 more)

### Community 47 - "Community 47"
Cohesion: 0.08
Nodes (7): When party-mode isn't installed, user override TOMLs are read directly., The wrapper knows the project root, so it must not let the resolver infer one…, TestAlias, TestBuildPool, TestOverrideMergeFallback, TestResolveParties, TestResolverInvocation

### Community 48 - "Community 48"
Cohesion: 0.13
Nodes (24): lib(), fixture, rows(), run(), test_categories_counts_sorted(), test_cli_bad_extra_and_missing_file(), test_cli_categories(), test_cli_extra_inline_json() (+16 more)

### Community 49 - "Community 49"
Cohesion: 0.08
Nodes (7): When party-mode isn't installed, user override TOMLs are read directly., The wrapper knows the project root, so it must not let the resolver infer one…, TestAlias, TestBuildPool, TestOverrideMergeFallback, TestResolveParties, TestResolverInvocation

### Community 50 - "Community 50"
Cohesion: 0.16
Nodes (20): calendar_entry_allowed(), DateTime, Pure time domain types and calendar-entry gate., Calendar may be entered only when a local DateTime exists., Named wall-clock fields shared by UTC and local snapshots., _days_in_month(), make_snapshot(), Pure UTC→local conversion and snapshot construction (no device imports). (+12 more)

### Community 51 - "Community 51"
Cohesion: 0.14
Nodes (22): Small shared provisioning constants. This module intentionally has no crypto or…, Cooperative PBKDF2 job stepper (≤N HMAC rounds per tick). Host-testable: no…, Small first-boot PBKDF2 derive job; loaded while setup scan is active., bytes_to_hex(), constant_time_equal(), hex_to_bytes(), _hmac_pads(), hmac_sha256() (+14 more)

### Community 52 - "Community 52"
Cohesion: 0.16
Nodes (24): Return ``ticks + delta_ms`` modulo PERIOD (delta may be negative)., ticks_add(), next_surface(), Return ``(next_surface, next_deadline)`` for a touch-surface evaluation. A…, _imported_roots(), Path, Host tests for pure Rotation/Bar touch-surface transitions., _remember_module() (+16 more)

### Community 53 - "Community 53"
Cohesion: 0.14
Nodes (3): Bounded store-credential STA connect/reconnect (no candidate)., Named station join/persist failure (no crash, no secret payload)., station_error_event()

### Community 54 - "Community 54"
Cohesion: 0.16
Nodes (20): _is_lowercase_hex(), Whole-record validation for the version-1 device settings object. Pure module:…, Parse JSON text and validate as a whole record., Outcome of validating a settings record as a whole., Validate a decoded settings object. Returns a :class:`ValidationResult`.…, _utf8_len(), validate_settings_json(), validate_settings_object() (+12 more)

### Community 55 - "Community 55"
Cohesion: 0.13
Nodes (18): Return generous hit geometry for the Settings reboot control., settings_reboot_item_rect(), Test a sampled point against the Settings reboot tap geometry., True when coords are valid integers outside the reboot tap target., Settings surface: status/guideline copy plus reboot control., Return the reboot button tap-target rect (x, y, w, h)., Return whether a point lies inside the reboot tap target., SettingsView (+10 more)

### Community 56 - "Community 56"
Cohesion: 0.10
Nodes (10): _Listen, _PartialClient, Regression coverage for the memory-footprint ownership boundaries., _serve_once(), _Sockets, test_kdf_cancel_is_terminal_and_compatible(), test_page_load_reuses_the_cache_and_rescan_forces_a_fresh_scan(), test_parser_release_drops_headers_and_body() (+2 more)

### Community 57 - "Community 57"
Cohesion: 0.15
Nodes (13): Poll once, returning ``(edge_down, x, y)`` without blocking., Return one raw touch edge per contact while safely handing off SPI0. The port…, TouchPort, FakePin, FakeSpi, _port(), Host coverage for TouchPort's bounded sampling and SPI0 ownership., _stable() (+5 more)

### Community 58 - "Community 58"
Cohesion: 0.14
Nodes (18): Single-writer App loop: snapshots, view rotation, tick deadlines., Duck-typed SyncCommand so App never imports ``src.device``., _SyncCommand, classify_local_rollover(), next_view_after_dwell(), Pure view-rotation and local-date rollover decisions (AD-12)., Classify a local civil-date change relative to a previous (y, m, d). Returns…, Decide the next active view when a dwell deadline expires. Clock → Calendar… (+10 more)

### Community 59 - "Community 59"
Cohesion: 0.10
Nodes (9): _days_in_month(), RTC-backed ClockPort (device layer only; AD-3)., Read/write UTC wall time through ``machine.RTC``. Only App should call this.…, Return a ``DateTime`` from the RTC, or ``None`` if cold/invalid., Write a ``DateTime`` into the RTC (UTC). Subseconds forced to 0., RtcClockPort, Host stand-in for the Pico's ``machine`` module. Only enough surface for the…, RTC (+1 more)

### Community 60 - "Community 60"
Cohesion: 0.09
Nodes (19): _module_level_tables(), fixture, parametrize, Memory budget gates for the Pico W build. The device fits a 179,328-byte GC…, Session and KDF state stay absent until an authenticated request., The web surface is host-testable only while it owns no device imports., The exact failure from the field: importing the chain a request needs., Free bytes are not enough; the first request needs a contiguous run. (+11 more)

### Community 61 - "Community 61"
Cohesion: 0.17
Nodes (21): _alias(), _brief(), build_pool(), _emit(), find_party_skill(), load_agents(), load_party_overrides(), load_party_workflow() (+13 more)

### Community 62 - "Community 62"
Cohesion: 0.17
Nodes (21): _alias(), _brief(), build_pool(), _emit(), find_party_skill(), load_agents(), load_party_overrides(), load_party_workflow() (+13 more)

### Community 63 - "Community 63"
Cohesion: 0.19
Nodes (17): centered_text(), draw_glyph(), draw_text(), 5x7 bitmap font, packed as a single ``bytes`` blob. The glyph table was a…, text_width(), parametrize, Glyph-level regression guard for the packed 5x7 font. The lit-pixel coordinates…, RecordingDisplay (+9 more)

### Community 64 - "Community 64"
Cohesion: 0.16
Nodes (9): Exception, Sole FS boundary for the ignored version-1 device settings record (AD-3)., Boot-time load with AD-3 restore/quarantine. Returns the canonical settings…, True when boot load yields a valid complete record., Atomically persist a complete version-1 record. Accepts Admin plaintext…, Named failure during atomic settings commit (no plaintext Admin)., Read/validate/commit the device-local ``.settings-v1`` record. Inject…, SettingsCommitError (+1 more)

### Community 65 - "Community 65"
Cohesion: 0.15
Nodes (8): KdfJob, Fresh salt hex after a successful derive (``None`` otherwise)., Derived verifier hex after a successful derive (``None`` otherwise)., Advance at most ``max_rounds`` HMAC rounds. Returns a terminal result code when…, Abandon the job and wipe secrets., Incremental PBKDF2-HMAC-SHA256 verify or derive for one Admin password., _wipe(), test_setup_kdf_failure_is_a_derive_failure_and_wipes_password()

### Community 66 - "Community 66"
Cohesion: 0.15
Nodes (20): _alias(), build_collective(), _emit(), find_group(), group_detail(), group_menu(), load_agents(), load_workflow() (+12 more)

### Community 67 - "Community 67"
Cohesion: 0.21
Nodes (20): ack(), add_target(), cmd_append(), cmd_init(), cmd_set(), entry_count(), main(), now() (+12 more)

### Community 68 - "Community 68"
Cohesion: 0.15
Nodes (20): _alias(), build_collective(), _emit(), find_group(), group_detail(), group_menu(), load_agents(), load_workflow() (+12 more)

### Community 69 - "Community 69"
Cohesion: 0.19
Nodes (18): _floor(), gregorian_to_lunar(), _jd_from_date(), _leap_month_offset(), _lunar_month11(), _new_moon_day(), Pure Vietnamese lunar (âm lịch) civil conversion — no hardware imports.…, Convert a Gregorian civil Y/M/D to Vietnamese lunar day/month/leap. Returns… (+10 more)

### Community 70 - "Community 70"
Cohesion: 0.13
Nodes (16): Legacy blocking WLAN / DNS / UDP NTP ops for worker-proof tests. Owns blocking…, Legacy threaded worker proof shell; not used by production composition. Owns…, Wrap-safe millisecond tick helpers (AD-5). Pure add/diff are host-testable…, Signed wrap-safe difference ``ticks1 - ticks2``. Result is in ``[-PERIOD/2,…, ticks_diff(), Pure Rotation/Bar touch-surface transition decisions., _imported_roots(), Path (+8 more)

### Community 71 - "Community 71"
Cohesion: 0.16
Nodes (3): _make_skill(), Path, ScannerTest

### Community 72 - "Community 72"
Cohesion: 0.16
Nodes (3): _make_skill(), Path, ScannerTest

### Community 73 - "Community 73"
Cohesion: 0.19
Nodes (7): NtpOps, _OpsError, Exception, Clamp UDP recv timeout to remaining SyncCommand deadline., Internal soft-fail carrying a SyncResult error_code., Injectable worker ops: ``run(command) -> SyncResult``. Optional ``wlan`` /…, Execute one bounded sync attempt for ``command``.

### Community 74 - "Community 74"
Cohesion: 0.17
Nodes (7): HttpRequest, IncrementalHttpParser, Completed HTTP request (method/path/headers/body)., Feed recv bytes until one request completes or a fixed error fires., Release request-owned buffers after routing transfers ownership., Consume ``data`` bytes. Returns ``(request_or_None, error_or_None, consumed)``., _Client

### Community 75 - "Community 75"
Cohesion: 0.13
Nodes (6): Validate an NTP response and convert its transmit timestamp to UTC., Advance one bounded unit of network work; never waits or sleeps., Schedule a store-credential station attempt (boot or reconnect)., A failed periodic sync while nominally online is ambiguous: it is both the only…, If a formerly-online station drops, start a reconnect attempt., Cancel mid-flight login/password-change KDF and drop held clients.

### Community 76 - "Community 76"
Cohesion: 0.19
Nodes (17): categories(), exclude(), filter_cats(), find(), fmt_categories(), fmt_rows(), load(), load_extra() (+9 more)

### Community 77 - "Community 77"
Cohesion: 0.19
Nodes (17): categories(), exclude(), filter_cats(), find(), fmt_categories(), fmt_rows(), load(), load_extra() (+9 more)

### Community 78 - "Community 78"
Cohesion: 0.18
Nodes (12): calibrate_touch_point(), CalibratedTouchPort, Map raw XPT2046 samples onto screen pixel coordinates. TouchPort deliberately…, Return ``(screen_x, screen_y)`` for a raw ``(x, y)`` touch sample., Wrap a raw TouchPort, translating its samples to screen pixels., _scale(), FakeTouchPort, Host coverage for raw-touch-to-screen-pixel calibration. (+4 more)

### Community 80 - "Community 80"
Cohesion: 0.16
Nodes (13): Package exports for the network boundary. Host-importable surface is limited to…, MailboxSaturationError, Exception, Pure capacity-one sync mailbox protocol (AD-8). Lock-free protocol object. App…, Publish exactly one terminal SyncResult into an empty result slot. If…, Result slot still occupied — contract violation (never overwrite)., Occupy the result slot without changing idle (proof contention plant). Raises…, True when ``now_ms`` is at or past ``deadline_ms`` (wrap-safe ticks). (+5 more)

### Community 81 - "Community 81"
Cohesion: 0.23
Nodes (15): blank_fences(), find_ad_issues(), find_frontmatter_placeholders(), find_placeholders(), find_unpinned_stack(), line_of(), lint(), main() (+7 more)

### Community 82 - "Community 82"
Cohesion: 0.23
Nodes (15): blank_fences(), find_ad_issues(), find_frontmatter_placeholders(), find_placeholders(), find_unpinned_stack(), line_of(), lint(), main() (+7 more)

### Community 83 - "Community 83"
Cohesion: 0.17
Nodes (5): NetworkWorker, One background thread that consumes SyncCommands and publishes SyncResults.…, Start the worker thread. Idempotent if already running., Request the worker loop to exit (best-effort; no join on MP)., Replace injectable network ops (proof scenario switching).

### Community 84 - "Community 84"
Cohesion: 0.19
Nodes (13): decode_ssid(), Pure SSID decode and dedupe for WLAN scan results. No ``machine``, ``network``,…, Extract deduplicated SSIDs from MicroPython-style scan rows. Each row may be a…, Decode a scan SSID to a displayable UTF-8 string. Accepts ``str`` or…, ssids_from_scan_rows(), _feed_all(), Host tests for pure setup HTTP parse/route and scan decode policy., The AP server's import footprint excludes admin-only resources. (+5 more)

### Community 85 - "Community 85"
Cohesion: 0.37
Nodes (12): _Cmd, _connected_wlan(), _fake_socket(), _ntp_payload(), _Secrets, test_ntp_ops_dns_fail(), test_ntp_ops_ntp_fail_on_kod_stratum_zero(), test_ntp_ops_ntp_fail_on_li_alarm() (+4 more)

### Community 86 - "Community 86"
Cohesion: 0.17
Nodes (10): Guards the analysis itself; an empty closure would silence every gate., test_boot_import_closure_is_derivable_and_non_trivial(), boot_resident_modules(), module_path(), module_scope_imports(), _ModuleScopeImports, Static import-graph analysis of what the Pico keeps resident. The heap cost…, Source path for a dotted ``src.*`` module, or None when it has none. (+2 more)

### Community 87 - "Community 87"
Cohesion: 0.17
Nodes (14): test_simulated_heap_is_within_budget(), deploy(), find_mpy_cross(), main(), Deploy main.py/src/secrets.py to a flashed Pico W, precompiling the largest…, Check the memory budgets before touching the device. A build that exceeds them…, run_memory_gate(), stage_tree() (+6 more)

### Community 88 - "Community 88"
Cohesion: 0.18
Nodes (14): find_micropython(), _load_deploy_module(), parse(), Exception, Drive the MicroPython heap simulation over the real deploy artifacts. The…, No MicroPython interpreter is available to run the simulation., Locate a MicroPython unix binary, or raise with build instructions., Import ``tools/deploy.py`` so staging cannot drift from deployment. (+6 more)

### Community 89 - "Community 89"
Cohesion: 0.22
Nodes (8): _format_date(), _format_hhmm(), _format_lunar(), _format_ss(), _label(), Dirty-region Clock view renderer (FR3 / UX-DR1–3/9)., AL · D/M or AL · D/M+ (leap); None when local is absent., _two_digit()

### Community 90 - "Community 90"
Cohesion: 0.20
Nodes (12): Memory budgets for the Pico W build. The device has a 179,328-byte GC heap.…, Modules added on top of the resident set to serve the admin site., station_web_modules(), compiled_sizes(), find_mpy_cross(), MpyCrossMissing, Exception, Compiled-size measurement for the deployable module set. (+4 more)

### Community 91 - "Community 91"
Cohesion: 0.27
Nodes (12): default_skills_root(), load_customize(), main(), parse_args(), Namespace, Path, Derive the skills root from this script's location. Layout assumption:…, Extract the `description:` value from a SKILL.md YAML frontmatter block.… (+4 more)

### Community 92 - "Community 92"
Cohesion: 0.29
Nodes (6): WordMetricsTest, main(), metrics(), Path, section_metrics(), word_count()

### Community 93 - "Community 93"
Cohesion: 0.27
Nodes (12): default_skills_root(), load_customize(), main(), parse_args(), Namespace, Path, Derive the skills root from this script's location. Layout assumption:…, Extract the `description:` value from a SKILL.md YAML frontmatter block.… (+4 more)

### Community 94 - "Community 94"
Cohesion: 0.29
Nodes (6): WordMetricsTest, main(), metrics(), Path, section_metrics(), word_count()

### Community 95 - "Community 95"
Cohesion: 0.33
Nodes (11): credentials_valid(), Host-safe Wi-Fi credential soft-check (no secrets in config)., Return True only when device-local secrets expose non-empty SSID and password.…, _clear_secrets(), _install_secrets(), Host tests for credentials soft-check., test_empty_ssid_is_invalid(), test_import_failure_other_than_import_error_is_invalid() (+3 more)

### Community 96 - "Community 96"
Cohesion: 0.29
Nodes (10): _emit(), _file_list(), _git_log(), JsonArgumentParser, main(), _parse_log(), _parse_numstat_line(), Turn one pass's log output into (commits, files_map). Shared by both. (+2 more)

### Community 97 - "Community 97"
Cohesion: 0.29
Nodes (10): _emit(), _file_list(), _git_log(), JsonArgumentParser, main(), _parse_log(), _parse_numstat_line(), Turn one pass's log output into (commits, files_map). Shared by both. (+2 more)

### Community 100 - "Community 100"
Cohesion: 0.24
Nodes (7): _hmac_sha256(), pbkdf2_hmac_sha256(), Pbkdf2Job, Native-emitted PBKDF2-HMAC-SHA256 fast path for MicroPython. This module keeps…, Incremental native-emitted PBKDF2 job for one 32-byte block., Run at most max_rounds and return the digest only at completion., Return PBKDF2-HMAC-SHA256 output for one 32-byte block.

### Community 101 - "Community 101"
Cohesion: 0.33
Nodes (8): _first_workspace(), _is_link_like(), main(), True when `path` redirects elsewhere: a POSIX symlink, or a Windows symlink OR…, Write every byte of `data` to `fd`. `os.write()` may write FEWER bytes than…, Write one event file into `events_dir`, refusing to follow a redirect. The…, _write_all(), _write_event()

### Community 102 - "Community 102"
Cohesion: 0.25
Nodes (7): boot_mode_for_settings(), Pure boot transition: unconfigured → SETUP_AP, else STATION_CONNECTING., True when consecutive terminal failures reach the setup fallback limit., Failure count after a successful persist/online station path., reset_station_failure_count(), station_failures_exhausted(), test_boot_mode_helpers_and_failure_count_policy()

### Community 103 - "Community 103"
Cohesion: 0.57
Nodes (7): _cleanup_device_stub(), _install_fake_machine(), _load_clock_port(), Host tests for RtcClockPort with a stubbed machine.RTC., test_cold_and_invalid_rtc_map_to_none(), test_set_utc_writes_rtc_tuple(), test_valid_rtc_tuple_maps_to_datetime()

### Community 109 - "Community 109"
Cohesion: 0.40
Nodes (5): _imported_roots(), Path, Record a module path and every dotted prefix (so src.device.foo hits…, _remember_module(), test_pure_modules_do_not_import_device_or_micropython_apis()

### Community 110 - "Community 110"
Cohesion: 0.70
Nodes (4): _emit(), _load(), main(), Runs inside MicroPython, inside the staged deploy tree. Imports the boot-…

## Knowledge Gaps
- **23 isolated node(s):** `crypto`, `fs`, `path`, `DEFAULT_CONFIG`, `SKIP_DIRECTORIES` (+18 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 1022 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `NetworkCoordinator` connect `Community 31` to `Community 33`, `Community 65`, `Community 102`, `Community 41`, `Community 42`, `Community 75`, `Community 107`, `Community 43`, `Community 45`, `Community 11`, `Community 80`, `Community 16`, `Community 50`, `Community 20`, `Community 53`, `Community 22`, `Community 27`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Why does `DateTime` connect `Community 50` to `Community 33`, `Community 2`, `Community 70`, `Community 103`, `Community 40`, `Community 73`, `Community 8`, `Community 75`, `Community 10`, `Community 43`, `Community 111`, `Community 15`, `Community 20`, `Community 85`, `Community 58`, `Community 59`, `Community 31`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Why does `App` connect `Community 27` to `Community 33`, `Community 2`, `Community 8`, `Community 43`, `Community 19`, `Community 20`, `Community 55`, `Community 58`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Are the 6 inferred relationships involving `NetworkCoordinator` (e.g. with `MailboxSaturationError` and `SyncResult`) actually correct?**
  _`NetworkCoordinator` has 6 INFERRED edges - model-reasoned connections that need verification._
- **What connects `crypto`, `fs`, `path` to the rest of the system?**
  _23 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.08209876543209876 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.08209876543209876 - nodes in this community are weakly interconnected._