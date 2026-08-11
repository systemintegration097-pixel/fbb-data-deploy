import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from db_manager import DBManager

def test_database():
    print("=== STARTING DATABASE VERIFICATION ===")
    
    # 1. Test Dashboard Stats
    print("\nTesting get_dashboard_stats()...")
    try:
        stats = DBManager.get_dashboard_stats()
        print("Success!")
        print(f"  Total Zones: {stats['total_zones']}")
        print(f"  Total Boxes: {stats['total_boxes']}")
        print(f"  Total Active Customers: {stats['total_active']}")
        print(f"  Average Saturation: {stats['avg_saturation']}%")
    except Exception as e:
        print(f"FAILED: {e}")
        return False
        
    # 2. Test Filter Options
    print("\nTesting get_filter_options()...")
    try:
        filters = DBManager.get_filter_options()
        print("Success!")
        print(f"  Branches count: {len(filters['branches'])}")
        print(f"  Departments count: {len(filters['departments'])}")
        print(f"  Partners count: {len(filters['partners'])}")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    # 3. Test Zones Query & Pagination
    print("\nTesting get_zones() pagination...")
    try:
        zones_res = DBManager.get_zones(page=1, per_page=5)
        print("Success!")
        print(f"  Total matched: {zones_res['total']}")
        print(f"  Rows returned: {len(zones_res['data'])}")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    # 4. Test Boxes Query & Pagination
    print("\nTesting get_boxes() pagination...")
    try:
        boxes_res = DBManager.get_boxes(page=1, per_page=5)
        print("Success!")
        print(f"  Total matched: {boxes_res['total']}")
        print(f"  Rows returned: {len(boxes_res['data'])}")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    # 5. Test Staff Query & Pagination
    print("\nTesting get_staff() pagination...")
    try:
        staff_res = DBManager.get_staff(page=1, per_page=5)
        print("Success!")
        print(f"  Total matched: {staff_res['total']}")
        print(f"  Rows returned: {len(staff_res['data'])}")
        if len(staff_res['data']) > 0:
            print(f"  First staff returned: {staff_res['data'][0]['staff_team']} (Zone: {staff_res['data'][0]['zone']})")
    except Exception as e:
        print(f"FAILED: {e}")
        return False

    # 6. Test CRUD for Zones (Including Staff Join check)
    print("\nTesting CRUD operations for ZONES...")
    try:
        # Create
        new_zone_data = {
            "zone": "TEST_Z01",
            "branch": "TST",
            "saturation": 0.456,
            "active_customers": 100,
            "status_service": "Online"
        }
        new_id = DBManager.add_zone(new_zone_data)
        print(f"  CREATE: Success! New Zone ID = {new_id}")
        
        # Read (Checks join as well, since there is no staff for TEST_Z01 yet, staff should be None)
        zone = DBManager.get_zone(new_id)
        print(f"  READ: Success! Zone retrieved = {zone['zone']}, Staff = {zone['staff']}")
        assert zone['zone'] == "TEST_Z01"
        assert zone['staff'] is None
        
        # Create a staff for this zone to test the join!
        new_staff_data = {
            "staff_team": "TEST_STAFF_MEMBER",
            "zone": "TEST_Z01",
            "branch": "TST",
            "partner": "TEST_PARTNER"
        }
        new_staff_id = DBManager.add_staff(new_staff_data)
        print(f"  CREATE STAFF FOR ZONE: Success! Staff ID = {new_staff_id}")
        
        # Read zone again, now should have staff!
        zone_with_staff = DBManager.get_zone(new_id)
        print(f"  READ WITH STAFF JOIN: Success! Staff name = {zone_with_staff['staff']['staff_team']}")
        assert zone_with_staff['staff'] is not None
        assert zone_with_staff['staff']['staff_team'] == "TEST_STAFF_MEMBER"
        
        # Clean up
        DBManager.delete_staff(new_staff_id)
        DBManager.delete_zone(new_id)
        print("  CLEANUP: CRUD Zones & Staff Join verified!")
        
    except Exception as e:
        print(f"FAILED CRUD ZONES/STAFF JOIN: {e}")
        return False

    # 7. Test CRUD for Staff Table
    print("\nTesting CRUD operations for STAFF...")
    try:
        new_staff_data = {
            "staff_team": "TEST_CRUD_TEAM",
            "zone": "TEST_Z99",
            "branch": "TST",
            "partner": "TST_PARTNER",
            "warranty_period": 45
        }
        new_id = DBManager.add_staff(new_staff_data)
        print(f"  CREATE: Success! ID = {new_id}")
        
        member = DBManager.get_staff_member(new_id)
        print(f"  READ: Success! retrieved = {member['staff_team']}, Warranty = {member['warranty_period']}")
        assert member['staff_team'] == "TEST_CRUD_TEAM"
        assert member['warranty_period'] == 45
        
        updated = DBManager.update_staff(new_id, {"staff_team": "TEST_CRUD_TEAM_UPDATED", "warranty_period": 90})
        print(f"  UPDATE: Success! changes = {updated}")
        
        member_upd = DBManager.get_staff_member(new_id)
        print(f"  READ UPDATED: Success! retrieved = {member_upd['staff_team']}, Warranty = {member_upd['warranty_period']}")
        assert member_upd['staff_team'] == "TEST_CRUD_TEAM_UPDATED"
        assert member_upd['warranty_period'] == 90
        
        deleted = DBManager.delete_staff(new_id)
        print(f"  DELETE: Success! affected = {deleted}")
        
        member_del = DBManager.get_staff_member(new_id)
        print(f"  VERIFY DELETED: Success! retrieved = {member_del}")
        assert member_del is None
        
    except Exception as e:
        print(f"FAILED CRUD STAFF: {e}")
        return False

    print("\n=== DATABASE VERIFICATION COMPLETED SUCCESSFULLY ===")
    return True

if __name__ == "__main__":
    success = test_database()
    sys.exit(0 if success else 1)
