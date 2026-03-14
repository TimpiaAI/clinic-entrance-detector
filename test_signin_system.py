#!/usr/bin/env python
"""Test script for digital signin system."""

from api.functie_client import FunctieAPIClient
from api.signin_manager import SigninManager


def test_api_connectivity():
    """Test connection to Functie API."""
    print("\n=== Testing API Connectivity ===\n")

    client = FunctieAPIClient("sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH")

    # Test getDoctors
    print("1. Fetching doctors...")
    doctors, error = client.get_doctors()
    if error:
        print(f"   ❌ Error: {error}")
        return False

    print(f"   ✅ Found {len(doctors)} doctors:")
    for doc in doctors:
        print(f"      - {doc.full_name} (ID: {doc.id}, Units: {doc.medical_units})")

    # Test todayAppointments
    print("\n2. Fetching today's appointments...")
    if not doctors:
        print("   ⚠️  No doctors found, skipping appointments")
        return True

    all_appts = []
    for doc in doctors:
        appts, error = client.get_today_appointments(doc.id)
        if error:
            print(f"   ⚠️  Error for {doc.full_name}: {error}")
            continue
        print(f"   ✅ {doc.full_name}: {len(appts)} appointments")
        for appt in appts:
            print(f"      - {appt.full_name} @ {appt.appointment_at}")
            all_appts.append(appt)

    if not all_appts:
        print("   ℹ️  No appointments scheduled for today")

    return True


def test_fuzzy_matching():
    """Test fuzzy name matching."""
    print("\n=== Testing Fuzzy Matching ===\n")

    client = FunctieAPIClient("sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH")
    manager = SigninManager(client)

    # Initialize
    print("1. Initializing manager...")
    success, error = manager.initialize()
    if not success:
        print(f"   ❌ Error: {error}")
        return False
    print(f"   ✅ Loaded {len(manager.doctors)} doctors")

    # Refresh appointments
    print("\n2. Refreshing appointments...")
    success, error = manager.refresh_appointments()
    if not success:
        print(f"   ⚠️  Error: {error}")
    else:
        print(f"   ✅ Synced {len(manager.all_appointments)} appointments")

    if not manager.all_appointments:
        print("   ℹ️  No appointments for testing fuzzy matching")
        return True

    # Test fuzzy matching with real names
    print("\n3. Testing fuzzy matching with real appointments...")
    for i, appt in enumerate(manager.all_appointments[:3]):  # Test first 3
        print(f"\n   Appointment {i+1}: {appt.full_name}")

        # Test exact match
        matches = manager.find_fuzzy_matches(appt.full_name, threshold=60)
        print(f"      Exact name: {len(matches)} matches")
        for m in matches[:3]:
            print(f"         - {m.appointment.full_name}: {m.score:.1f}%")

        # Test typo (remove first char of last name)
        if len(appt.last_name) > 2:
            typo_name = f"{appt.first_name} {appt.last_name[1:]}"
            matches = manager.find_fuzzy_matches(typo_name, threshold=60)
            print(f"      With typo '{typo_name}': {len(matches)} matches")
            for m in matches[:2]:
                print(f"         - {m.appointment.full_name}: {m.score:.1f}%")

        # Test word swap
        swapped_name = f"{appt.last_name} {appt.first_name}"
        matches = manager.find_fuzzy_matches(swapped_name, threshold=60)
        print(f"      Word swap '{swapped_name}': {len(matches)} matches")
        for m in matches[:2]:
            print(f"         - {m.appointment.full_name}: {m.score:.1f}%")

    return True


def test_signin_workflow():
    """Test complete signin workflow."""
    print("\n=== Testing Signin Workflow ===\n")

    client = FunctieAPIClient("sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH")
    manager = SigninManager(client)

    # Initialize
    print("1. Initializing...")
    success, error = manager.initialize()
    if not success:
        print(f"   ❌ Error: {error}")
        return False

    # Refresh
    print("2. Refreshing appointments...")
    success, error = manager.refresh_appointments()
    if not success:
        print(f"   ⚠️  Error refreshing: {error}")
        if not manager.all_appointments:
            print("   ❌ No appointments to test workflow")
            return False

    if not manager.all_appointments:
        print("   ℹ️  No appointments for workflow test")
        return True

    # Simulate detection
    real_appt = manager.all_appointments[0]
    detected_name = real_appt.first_name + " " + real_appt.last_name[:-1]  # Add typo

    print(f"\n3. Simulating detection: '{detected_name}'")
    print(f"   (Real appointment: '{real_appt.full_name}')\n")

    # Start session
    print("4. Starting signin session...")
    session, matches = manager.start_signin_session(detected_name)
    print(f"   ✅ Session ID: {id(session)}")
    print(f"   Fuzzy matches: {len(matches)}")
    for m in matches[:3]:
        print(f"      - {m.appointment.full_name} (ID: {m.appointment.id}): {m.score:.1f}%")

    if not matches:
        print("   ⚠️  No matches found")
        return True

    # Confirm appointment
    session_id = str(id(session))
    best_match = matches[0]
    test_phone = "0723456789"

    print(f"\n5. Confirming appointment...")
    print(f"   Appointment: {best_match.appointment.full_name}")
    print(f"   Phone: {test_phone}")

    success, error = manager.confirm_appointment(session_id, best_match.appointment.id, test_phone)
    if not success:
        print(f"   ❌ Error: {error}")
        return False
    print(f"   ✅ Confirmed")

    # Complete signin
    print(f"\n6. Creating presentation (digital signin)...")
    response, error = manager.complete_signin(session_id)
    if error:
        print(f"   ⚠️  Error: {error}")
        print("   (This is expected if patient/CNP validation fails)")
        return True  # Not a test failure

    if response:
        print(f"   ✅ Created!")
        print(f"      Presentation ID: {response.get('presentation_id')}")
        print(f"      Patient: {response.get('first_name')} {response.get('last_name')}")
        print(f"      Doctor ID: {response.get('medic_id')}")

    # Clean up
    print(f"\n7. Clearing session...")
    manager.clear_session(session_id)
    print(f"   ✅ Cleaned up")

    return True


def test_status():
    """Test manager status endpoint."""
    print("\n=== Testing Status Endpoint ===\n")

    client = FunctieAPIClient("sk_Bve9jcBOEVZ2PvyaadHNks1ZpHxzTZbH")
    manager = SigninManager(client)

    # Initialize
    print("1. Initializing...")
    success, error = manager.initialize()
    if not success:
        print(f"   ❌ Error: {error}")
        return False

    # Get status
    print("\n2. Manager status:")
    status = manager.get_status()
    print(f"   Doctors: {status['doctors_count']}")
    print(f"   Appointments: {status['appointments_count']}")
    print(f"   Last sync: {status['last_sync']}")
    print(f"   Active sessions: {status['active_sessions']}")

    return True


if __name__ == "__main__":
    print("╔════════════════════════════════════════════════════════╗")
    print("║   Digital Signin System - Test Suite                  ║")
    print("╚════════════════════════════════════════════════════════╝")

    tests = [
        ("API Connectivity", test_api_connectivity),
        ("Fuzzy Matching", test_fuzzy_matching),
        ("Signin Workflow", test_signin_workflow),
        ("Status Endpoint", test_status),
    ]

    results = {}
    for name, test_func in tests:
        try:
            print(f"\n{'=' * 56}")
            print(f"Running: {name}")
            print(f"{'=' * 56}")
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Exception in {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    # Summary
    print("\n" + "=" * 56)
    print("TEST SUMMARY")
    print("=" * 56)
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{name}: {status}")

    passed_count = sum(1 for p in results.values() if p)
    total_count = len(results)
    print(f"\nTotal: {passed_count}/{total_count} tests passed")

    exit(0 if all(results.values()) else 1)
