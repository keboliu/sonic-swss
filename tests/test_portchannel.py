import time
import re
import json
import pytest
import itertools

from swsscommon import swsscommon


class TestPortchannel(object):
    def test_Portchannel(self, dvs, testlog):

        # create port channel
        db = swsscommon.DBConnector(0, dvs.redis_sock, 0)
        ps = swsscommon.ProducerStateTable(db, "LAG_TABLE")
        fvs = swsscommon.FieldValuePairs([("admin", "up"), ("mtu", "1500")])

        ps.set("PortChannel0001", fvs)

        # create port channel member
        ps = swsscommon.ProducerStateTable(db, "LAG_MEMBER_TABLE")
        fvs = swsscommon.FieldValuePairs([("status", "enabled")])

        ps.set("PortChannel0001:Ethernet0", fvs)

        time.sleep(1)

        # check asic db
        asicdb = swsscommon.DBConnector(1, dvs.redis_sock, 0)

        lagtbl = swsscommon.Table(asicdb, "ASIC_STATE:SAI_OBJECT_TYPE_LAG")
        lags = lagtbl.getKeys()
        assert len(lags) == 1

        lagmtbl = swsscommon.Table(asicdb, "ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER")
        lagms = lagmtbl.getKeys()
        assert len(lagms) == 1

        (status, fvs) = lagmtbl.get(lagms[0])
        fvs = dict(fvs)
        assert status
        assert "SAI_LAG_MEMBER_ATTR_LAG_ID" in fvs
        assert fvs.pop("SAI_LAG_MEMBER_ATTR_LAG_ID") == lags[0]
        assert "SAI_LAG_MEMBER_ATTR_PORT_ID" in fvs
        assert dvs.asicdb.portoidmap[fvs.pop("SAI_LAG_MEMBER_ATTR_PORT_ID")] == "Ethernet0"
        assert "SAI_LAG_MEMBER_ATTR_INGRESS_DISABLE" in fvs
        assert fvs.pop("SAI_LAG_MEMBER_ATTR_INGRESS_DISABLE") == "false"
        assert "SAI_LAG_MEMBER_ATTR_EGRESS_DISABLE" in fvs
        assert fvs.pop("SAI_LAG_MEMBER_ATTR_EGRESS_DISABLE") == "false"
        assert not fvs

        ps = swsscommon.ProducerStateTable(db, "LAG_MEMBER_TABLE")
        fvs = swsscommon.FieldValuePairs([("status", "disabled")])

        ps.set("PortChannel0001:Ethernet0", fvs)

        time.sleep(1)

        lagmtbl = swsscommon.Table(asicdb, "ASIC_STATE:SAI_OBJECT_TYPE_LAG_MEMBER")
        lagms = lagmtbl.getKeys()
        assert len(lagms) == 1

        (status, fvs) = lagmtbl.get(lagms[0])
        fvs = dict(fvs)
        assert status
        assert "SAI_LAG_MEMBER_ATTR_LAG_ID" in fvs
        assert fvs.pop("SAI_LAG_MEMBER_ATTR_LAG_ID") == lags[0]
        assert "SAI_LAG_MEMBER_ATTR_PORT_ID" in fvs
        assert dvs.asicdb.portoidmap[fvs.pop("SAI_LAG_MEMBER_ATTR_PORT_ID")] == "Ethernet0"
        assert "SAI_LAG_MEMBER_ATTR_INGRESS_DISABLE" in fvs
        assert fvs.pop("SAI_LAG_MEMBER_ATTR_INGRESS_DISABLE") == "true"
        assert "SAI_LAG_MEMBER_ATTR_EGRESS_DISABLE" in fvs
        assert fvs.pop("SAI_LAG_MEMBER_ATTR_EGRESS_DISABLE") == "true"
        assert not fvs

        # remove port channel member
        ps = swsscommon.ProducerStateTable(db, "LAG_MEMBER_TABLE")
        ps._del("PortChannel0001:Ethernet0")

        # remove port channel
        ps = swsscommon.ProducerStateTable(db, "LAG_TABLE")
        ps._del("PortChannel0001")

        time.sleep(1)

        # check asic db
        lags = lagtbl.getKeys()
        assert len(lags) == 0

        lagms = lagmtbl.getKeys()
        assert len(lagms) == 0

    def test_Portchannel_lacpkey(self, dvs, testlog):
        portchannelNamesAuto = [("PortChannel001", "Ethernet0", 1001),
                            ("PortChannel002", "Ethernet4", 1002),
                            ("PortChannel2", "Ethernet8", 12),
                            ("PortChannel000", "Ethernet12", 1000)]

        portchannelNames = [("PortChannel0003", "Ethernet16", 0),
                            ("PortChannel0004", "Ethernet20", 0),
                            ("PortChannel0005", "Ethernet24", 564)]

        self.cdb = swsscommon.DBConnector(4, dvs.redis_sock, 0)

        # Create PortChannels
        tbl = swsscommon.Table(self.cdb, "PORTCHANNEL")
        fvs = swsscommon.FieldValuePairs(
            [("admin_status", "up"), ("mtu", "9100"), ("oper_status", "up"), ("lacp_key", "auto")])

        for portchannel in portchannelNamesAuto:
            tbl.set(portchannel[0], fvs)
            
        fvs_no_lacp_key = swsscommon.FieldValuePairs(
            [("admin_status", "up"), ("mtu", "9100"), ("oper_status", "up")])
        tbl.set(portchannelNames[0][0], fvs_no_lacp_key)

        fvs_empty_lacp_key = swsscommon.FieldValuePairs(
            [("admin_status", "up"), ("mtu", "9100"), ("oper_status", "up"), ("lacp_key", "")])
        tbl.set(portchannelNames[1][0], fvs_empty_lacp_key)

        fvs_set_number_lacp_key = swsscommon.FieldValuePairs(
            [("admin_status", "up"), ("mtu", "9100"), ("oper_status", "up"), ("lacp_key", "564")])
        tbl.set(portchannelNames[2][0], fvs_set_number_lacp_key)
        time.sleep(1)

        # Add members to PortChannels
        tbl = swsscommon.Table(self.cdb, "PORTCHANNEL_MEMBER")
        fvs = swsscommon.FieldValuePairs([("NULL", "NULL")])

        for portchannel in itertools.chain(portchannelNames, portchannelNamesAuto):
            tbl.set(portchannel[0] + "|" + portchannel[1], fvs)
        time.sleep(1)

        #  TESTS here that LACP key is valid and equls to the expected LACP key
        #  The expected LACP key in the number at the end of the Port-Channel name with a prefix '1'
        for portchannel in itertools.chain(portchannelNames, portchannelNamesAuto):
            (exit_code, output) = dvs.runcmd("teamdctl " + portchannel[0] + " state dump")
            port_state_dump = json.loads(output)
            lacp_key = port_state_dump["ports"][portchannel[1]]["runner"]["actor_lacpdu_info"]["key"]
            assert lacp_key == portchannel[2]

        # remove PortChannel members
        tbl = swsscommon.Table(self.cdb, "PORTCHANNEL_MEMBER")
        for portchannel in itertools.chain(portchannelNames, portchannelNamesAuto):
            tbl._del(portchannel[0] + "|" + portchannel[1])
        time.sleep(1)

        # remove PortChannel
        tbl = swsscommon.Table(self.cdb, "PORTCHANNEL")
        for portchannel in itertools.chain(portchannelNames, portchannelNamesAuto):
            tbl._del(portchannel[0])
        time.sleep(1)

    def test_Portchannel_oper_down(self, dvs, testlog):

        self.adb = swsscommon.DBConnector(1, dvs.redis_sock, 0)
        self.cdb = swsscommon.DBConnector(4, dvs.redis_sock, 0)
        self.pdb = swsscommon.DBConnector(0, dvs.redis_sock, 0)

        # Create 4 PortChannels
        tbl = swsscommon.Table(self.cdb, "PORTCHANNEL")
        fvs = swsscommon.FieldValuePairs([("admin_status", "up"),("mtu", "9100"),("oper_status", "up")])

        tbl.set("PortChannel001", fvs)
        time.sleep(1)
        tbl.set("PortChannel002", fvs)
        time.sleep(1)
        tbl.set("PortChannel003", fvs)
        time.sleep(1)
        tbl.set("PortChannel004", fvs)
        time.sleep(1)

        tbl = swsscommon.Table(self.cdb, "PORTCHANNEL_MEMBER")
        fvs = swsscommon.FieldValuePairs([("NULL", "NULL")])
        tbl.set("PortChannel001|Ethernet0", fvs)
        time.sleep(1)
        tbl.set("PortChannel002|Ethernet4", fvs)
        time.sleep(1)
        tbl.set("PortChannel003|Ethernet8", fvs)
        time.sleep(1)
        tbl.set("PortChannel004|Ethernet12", fvs)
        time.sleep(1)

        tbl = swsscommon.Table(self.cdb, "PORTCHANNEL_INTERFACE")
        fvs = swsscommon.FieldValuePairs([("NULL", "NULL")])
        tbl.set("PortChannel001", fvs)
        tbl.set("PortChannel001|40.0.0.0/31", fvs)
        time.sleep(1)
        tbl.set("PortChannel002", fvs)
        tbl.set("PortChannel002|40.0.0.2/31", fvs)
        time.sleep(1)
        tbl.set("PortChannel003", fvs)
        tbl.set("PortChannel003|40.0.0.4/31", fvs)
        time.sleep(1)
        tbl.set("PortChannel004", fvs)
        tbl.set("PortChannel004|40.0.0.6/31", fvs)
        time.sleep(1)

        # check application database
        tbl = swsscommon.Table(self.pdb, "INTF_TABLE:PortChannel001")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 1
        assert intf_entries[0] == "40.0.0.0/31"
        tbl = swsscommon.Table(self.pdb, "INTF_TABLE:PortChannel002")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 1
        assert intf_entries[0] == "40.0.0.2/31"
        tbl = swsscommon.Table(self.pdb, "INTF_TABLE:PortChannel003")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 1
        assert intf_entries[0] == "40.0.0.4/31"
        tbl = swsscommon.Table(self.pdb, "INTF_TABLE:PortChannel004")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 1
        assert intf_entries[0] == "40.0.0.6/31"


        # set oper_status for PortChannels
        ps = swsscommon.ProducerStateTable(self.pdb, "LAG_TABLE")
        fvs = swsscommon.FieldValuePairs([("admin_status", "up"),("mtu", "9100"),("oper_status", "up")])
        ps.set("PortChannel001", fvs)
        ps.set("PortChannel002", fvs)
        ps.set("PortChannel003", fvs)
        ps.set("PortChannel004", fvs)
        time.sleep(1)

        dvs.runcmd("arp -s 40.0.0.1 00:00:00:00:00:01")
        time.sleep(1)
        dvs.runcmd("arp -s 40.0.0.3 00:00:00:00:00:03")
        time.sleep(1)
        dvs.runcmd("arp -s 40.0.0.5 00:00:00:00:00:05")
        time.sleep(1)
        dvs.runcmd("arp -s 40.0.0.7 00:00:00:00:00:07")
        time.sleep(1)

        ps = swsscommon.ProducerStateTable(self.pdb, "ROUTE_TABLE")
        fvs = swsscommon.FieldValuePairs([("nexthop","40.0.0.1,40.0.0.3,40.0.0.5,40.0.0.7"), ("ifname", "PortChannel001,PortChannel002,PortChannel003,PortChannel004")])

        ps.set("2.2.2.0/24", fvs)
        time.sleep(1)

        # check if route has propagated to ASIC DB
        re_tbl = swsscommon.Table(self.adb, "ASIC_STATE:SAI_OBJECT_TYPE_ROUTE_ENTRY")

        found_route = False
        for key in re_tbl.getKeys():
            route = json.loads(key)
            if route["dest"] == "2.2.2.0/24":
               found_route = True
               break

        assert found_route

        # check if route points to next hop group
        nhg_tbl = swsscommon.Table(self.adb, "ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP_GROUP")
        (status, fvs) = re_tbl.get(key)
        for v in fvs:
            if v[0] == "SAI_ROUTE_ENTRY_ATTR_NEXT_HOP_ID":
                nhg_id = v[1]

        (status, fvs) = nhg_tbl.get(nhg_id)
        assert status

        # check if next hop group consists of 4 members
        nhg_member_tbl = swsscommon.Table(self.adb, "ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP_GROUP_MEMBER")
        keys = nhg_member_tbl.getKeys()
        assert len(keys) == 4

        for key in keys:
            (status, fvs) = nhg_member_tbl.get(key)
            for v in fvs:
                if v[0] == "SAI_NEXT_HOP_GROUP_MEMBER_ATTR_NEXT_HOP_GROUP_ID":
                    assert v[1] == nhg_id

        # bring PortChannel down
        dvs.servers[0].runcmd("ip link set down dev eth0")
        time.sleep(1)
        ps = swsscommon.ProducerStateTable(self.pdb, "LAG_TABLE")
        fvs = swsscommon.FieldValuePairs([("admin_status", "up"),("mtu", "9100"),("oper_status", "down")])
        ps.set("PortChannel001", fvs)
        time.sleep(1)

        # check if next hop group consists of 3 member
        keys = nhg_member_tbl.getKeys()
        assert len(keys) == 3

        # remove IP address
        tbl = swsscommon.Table(self.cdb, "PORTCHANNEL_INTERFACE")
        tbl._del("PortChannel001|40.0.0.0/31")
        tbl._del("PortChannel002|40.0.0.2/31")
        tbl._del("PortChannel003|40.0.0.4/31")
        tbl._del("PortChannel004|40.0.0.6/31")
        time.sleep(1)

        # check application database
        tbl = swsscommon.Table(self.pdb, "INTF_TABLE:PortChannel001")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 0

        tbl = swsscommon.Table(self.pdb, "INTF_TABLE:PortChannel002")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 0

        tbl = swsscommon.Table(self.pdb, "INTF_TABLE:PortChannel003")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 0

        tbl = swsscommon.Table(self.pdb, "INTF_TABLE:PortChannel004")
        intf_entries = tbl.getKeys()
        assert len(intf_entries) == 0

        # remove PortChannel members
        tbl = swsscommon.Table(self.cdb, "PORTCHANNEL_MEMBER")
        tbl._del("PortChannel001|Ethernet0")
        tbl._del("PortChannel002|Ethernet4")
        tbl._del("PortChannel003|Ethernet8")
        tbl._del("PortChannel004|Ethernet12")
        time.sleep(1)

        # remove PortChannel
        tbl = swsscommon.Table(self.cdb, "PORTCHANNEL")
        tbl._del("PortChannel001")
        tbl._del("PortChannel002")
        tbl._del("PortChannel003")
        tbl._del("PortChannel004")
        time.sleep(1)

        # Restore eth0 up
        dvs.servers[0].runcmd("ip link set up dev eth0")
        time.sleep(1)


# Add Dummy always-pass test at end as workaroud
# for issue when Flaky fail on final test it invokes module tear-down before retrying
def test_nonflaky_dummy():
    pass
