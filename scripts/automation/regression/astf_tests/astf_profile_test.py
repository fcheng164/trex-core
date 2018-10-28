from .astf_general_test import CASTFGeneral_Test, CTRexScenario
import os, sys
from misc_methods import run_command
from trex.astf.api import *
import time
from trex.stl.trex_stl_packet_builder_scapy import ip2int, int2ip
import pprint
import random



class ASTFProfile_Test(CASTFGeneral_Test):
    """Checking some profiles """
    def setUp(self):
        CASTFGeneral_Test.setUp(self)
        c = self.astf_trex;
        assert(c.is_connected())
        self.weak = self.is_VM
        self.skip_test_trex_522 =False;
        setup= CTRexScenario.setup_name;
        if setup in ['trex19','trex07','trex23']:
            self.skip_test_trex_522 =True;
        self.driver_params = self.get_driver_params()

    def get_profile_by_name (self,name):
        profiles_path = os.path.join(CTRexScenario.scripts_path, 'astf/'+name)
        return(profiles_path)

    def check_cnt (self,c,name,val):
        if name not in c:
            self.fail('counter %s is not in counters ' %(name) )
        if c[name] != val:
            self.fail('counter {0} expect {1} value {2}  '.format(name,val,c[name]) )

    def validate_cnt (self,val1,val2,str_err):
        if val1 !=val2:
            self.fail('%s ' %(str_err))

    def check_tcp (self,stats):
        t=stats['traffic']
        c=t['client']
        self.check_cnt(c,'m_active_flows',0)
        self.check_cnt(c,'tcps_connects',c['tcps_closed'])
        s=t['server']
        self.check_cnt(s,'m_active_flows',0)
        self.check_cnt(s,'tcps_accepts',s['tcps_closed'])

        self.validate_cnt (c['tcps_sndbyte'],s['tcps_rcvbyte'],"tcps_sndbyte != tcps_rcvbyte")
        self.validate_cnt (s['tcps_sndbyte'],c['tcps_rcvbyte'],"tcps_sndbyte != tcps_rcvbyte")


    def check_udp (self,stats):
        t=stats['traffic']
        c=t['client']
        self.check_cnt(c,'m_active_flows',0)
        self.check_cnt(c,'udps_connects',c['udps_closed'])
        s=t['server']
        self.check_cnt(s,'m_active_flows',0)
        self.check_cnt(s,'udps_accepts',s['udps_closed'])
        if not self.skip_test_trex_522:
          self.validate_cnt (c['udps_sndpkt'],s['udps_rcvpkt'],"udps_sndpkt != udps_rcvpkt")
          self.validate_cnt (s['udps_sndpkt'],c['udps_rcvpkt'],"udps_sndpkt != udps_rcvpkt")
          self.validate_cnt (c['udps_sndbyte'],s['udps_rcvbyte'],"udps_sndbyte != udps_rcvbyte")
          self.validate_cnt (s['udps_sndbyte'],c['udps_rcvbyte'],"udps_sndbyte != udps_rcvbyte")

    def check_counters (self,stats,is_udp,is_tcp):

        c=self.astf_trex;
        valid_error =[]
        if self.weak:
           valid_error += ['__last','err_no_tcp','err_redirect_rx','tcps_rexmttimeo','tcps_sndrexmitbyte','tcps_sndrexmitpack','udps_keepdrops'];
        if self.skip_test_trex_522:
           valid_error += ['udps_keepdrops']

        r=c.is_traffic_stats_error(stats['traffic'])
        if (not r[0]):
            is_error = False
        else:
            if len(valid_error):
               is_error = (len(set(valid_error).intersection(r[1].keys()))>0) # accept some errors in vm
            else:
               is_error = True

        if is_error:
            pprint.pprint(stats)
            pprint.pprint(r[1])
            self.fail('ERROR in counters')

        # no errors 
        if is_tcp:
            self.check_tcp(stats)

        if is_udp:
            self.check_udp(stats)

    def check_latency_stats (self, all_stats):
        if not self.driver_params['latency_9k_enable']:
            return

        for port_id, port_stats in all_stats.items():
            hist = port_stats['hist']

            for k in ['s_avg', 'min_usec']:
               if hist[k] > self.driver_params['latency_9k_max_average']:
                   self.fail('%s latency is bigger (%s) than normal port-%s' % (k, hist[k], port_id))

            for k in ['s_max']:
               if hist[k] > self.driver_params['latency_9k_max_latency']:
                   self.fail('%s latency is bigger (%s) than normal port-%s' % (k, hist[k], port_id))

            # todo check the latency histogram 
            counters = port_stats['stats']

            for k in ['m_l3_cs_err','m_l4_cs_err','m_length_error','m_no_id','m_no_ipv4_option','m_no_magic','m_seq_error','m_tx_pkt_err']:
                if counters[k] > 0:
                    self.fail('error in latency port-%s, key: %s, val: %s' % (port_id, k, counters[k]))


    def run_astf_profile(self, profile_name, m, is_udp, is_tcp, ipv6 =False, check_counters=True, nc = False):
        c = self.astf_trex;

        if ipv6 and self.driver_params.get('no_ipv6', False):
            return

        c.reset();
        d = self.get_duration()
        print('starting profile %s for duration %s' % (profile_name, d))
        c.load_profile(self.get_profile_by_name(profile_name))
        c.clear_stats()
        c.start(duration = d,nc= nc,mult = m,ipv6 = ipv6,latency_pps = 1000)
        c.wait_on_traffic()
        stats = c.get_stats()
        pprint.pprint(stats['traffic'])
        print("latency stats:")
        pprint.pprint(stats['latency'])
        if check_counters:
            self.check_counters(stats,is_udp,is_tcp)
            self.check_latency_stats(stats['latency'])
            if c.get_warnings():
                print('\n\n*** test had warnings ****\n\n')
                for w in c.get_warnings():
                    print(w)

        print("PASS")

    def get_simple_params(self):
        tests = [ {'name': 'http_simple.py','is_tcp' :True,'is_udp':False,'default':True},
                  {'name': 'udp_pcap.py','is_tcp' :False,'is_udp':True,'default':False}
                  ]
        return (tests);

    def get_sfr_params(self):
        tests = [ {'name': 'sfr.py','is_tcp' :True,'is_udp':False,'m':1.0},
                  {'name': 'sfr_full.py','is_tcp' :True,'is_udp':True,'m':2.0}
                ]
        return (tests);

    def get_duration (self):
        #return random.randint(20, 120)
        #return 120
        return 10

    def test_astf_prof_simple(self):
        mult  = self.get_benchmark_param('multiplier',test_name = 'test_tcp_http')
        tests = self.get_simple_params() 
        for o in tests:
           self.run_astf_profile(o['name'],mult,o['is_udp'],o['is_tcp'])

        mult  = self.get_benchmark_param('multiplier',test_name = 'test_ipv6_tcp_http')
        for o in tests:
          self.run_astf_profile(o['name'],mult,o['is_udp'],o['is_tcp'],ipv6=True)

    def test_astf_prof_sfr(self):
        mult  = self.get_benchmark_param('multiplier',test_name = 'test_tcp_sfr')
        tests = self.get_sfr_params() 
        for o in tests:
           self.run_astf_profile(o['name'],mult*o['m'],o['is_udp'],o['is_tcp'])

    def test_astf_prof_no_crash_sfr(self):
        return;
        mult  = self.get_benchmark_param('multiplier',test_name = 'test_tcp_sfr_no_crash')
        tests = self.get_sfr_params() 
        for o in tests:
           for i_ipv6 in (True,False):
               self.run_astf_profile(o['name'],mult*o['m'],o['is_udp'],o['is_tcp'],ipv6=i_ipv6,check_counters=False,nc=True)
