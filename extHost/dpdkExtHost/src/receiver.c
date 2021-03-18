
#include <stdint.h>
#include <stdio.h> 
#include <unistd.h>
#include <inttypes.h>
#include <rte_eal.h>
#include <rte_ethdev.h>
#include <rte_cycles.h>
#include <rte_lcore.h>
#include <rte_mbuf.h>

#define RX_RING_SIZE 1024
#define TX_RING_SIZE 1024

#define NUM_MBUFS 8191
#define MBUF_CACHE_SIZE 250
#define BURST_SIZE 32

//uncomment this for debugging and recompile on external host!
//#define DEBUG

struct packet_data {
	uint64_t t_stamp1;
	uint64_t t_stamp2;
	uint64_t packet_sizes;
	struct packet_data *next;
};

uint16_t stop_cntr = 0;
static int checkStopFlag(void){
	stop_cntr += 1;
	if(stop_cntr != 0)
		return 0;
	if( access( "receiver_stop", F_OK ) != -1 ) {
		return 1;
	}
		return 0;
}

static const struct rte_eth_conf port_conf_default = {
	.rxmode = {
		.max_rx_pkt_len = RTE_ETHER_MAX_LEN,
	},
};

char* fname;

/*
 * Initializes a given port using global settings and with the RX buffers
 * coming from the mbuf_pool passed as a parameter.
 */
static inline int
port_init(uint16_t port, struct rte_mempool *mbuf_pool)
{
	struct rte_eth_conf port_conf = port_conf_default;
	const uint16_t rx_rings = 1, tx_rings = 1;
	uint16_t nb_rxd = RX_RING_SIZE;
	uint16_t nb_txd = TX_RING_SIZE;
	int retval;
	uint16_t q;
	struct rte_eth_dev_info dev_info;
	struct rte_eth_txconf txconf;

	printf("Init port %u \n", port);

	if (!rte_eth_dev_is_valid_port(port))
		return -1;

	retval = rte_eth_dev_info_get(port, &dev_info);
	if (retval != 0) {
		printf("Error during getting device (port %u) info: %s\n",
				port, strerror(-retval));
		return retval;
	}

	if (dev_info.tx_offload_capa & DEV_TX_OFFLOAD_MBUF_FAST_FREE)
		port_conf.txmode.offloads |=
			DEV_TX_OFFLOAD_MBUF_FAST_FREE;

	/* Configure the Ethernet device. */
	retval = rte_eth_dev_configure(port, rx_rings, tx_rings, &port_conf);
	if (retval != 0)
		return retval;

	retval = rte_eth_dev_adjust_nb_rx_tx_desc(port, &nb_rxd, &nb_txd);
	if (retval != 0)
		return retval;

	/* Allocate and set up 1 RX queue per Ethernet port. */
	for (q = 0; q < rx_rings; q++) {
		retval = rte_eth_rx_queue_setup(port, q, nb_rxd,
				rte_eth_dev_socket_id(port), NULL, mbuf_pool);
		if (retval < 0)
			return retval;
	}

	txconf = dev_info.default_txconf;
	txconf.offloads = port_conf.txmode.offloads;
	/* Allocate and set up 1 TX queue per Ethernet port. */
	for (q = 0; q < tx_rings; q++) {
		retval = rte_eth_tx_queue_setup(port, q, nb_txd,
				rte_eth_dev_socket_id(port), &txconf);
		if (retval < 0)
			return retval;
	}

	/* Start the Ethernet port. */
	retval = rte_eth_dev_start(port);
	if (retval < 0)
		return retval;

	/* Display the port MAC address. */
	struct rte_ether_addr addr;
	retval = rte_eth_macaddr_get(port, &addr);
	if (retval != 0)
		return retval;

	printf("Port %u MAC: %02" PRIx8 " %02" PRIx8 " %02" PRIx8
			   " %02" PRIx8 " %02" PRIx8 " %02" PRIx8 "\n",
			port,
			addr.addr_bytes[0], addr.addr_bytes[1],
			addr.addr_bytes[2], addr.addr_bytes[3],
			addr.addr_bytes[4], addr.addr_bytes[5]);

	/* Enable RX in promiscuous mode for the Ethernet device. */
	retval = rte_eth_promiscuous_enable(port);
	if (retval != 0)
		return retval;

	return 0;
}

/*
 * The lcore main. This is the main thread that does the work, reading from
 * an input port and writing to an output port.
 */
static void lcore_main(void) {
	uint16_t port;
	port = 0;

	/*
	 * Check that the port is on the same NUMA node as the polling thread
	 * for best performance.
	 */
	if (rte_eth_dev_socket_id(port) > 0 && rte_eth_dev_socket_id(port) != (int)rte_socket_id())
		printf("WARNING, port %u is on remote NUMA node to "
				"polling thread.\n\tPerformance will "
				"not be optimal.\n", port);

	printf("\nCore %u Capturing packets. [Ctrl+C to quit]\n", rte_lcore_id());

	uint64_t raw_packet_counter = 0;
	struct packet_data *first = NULL;
	struct packet_data *last = NULL;


	FILE *status = fopen("receiver_finished.log", "w");
	fprintf(status, "False");
	fclose(status);

	/* Run until the application is quit or killed. */
	for (;;) {

		if(checkStopFlag()) break; //TODO

		/* Get burst of RX packets, from first port of pair. */
		struct rte_mbuf *bufs[BURST_SIZE];
		const uint16_t nb_rx = rte_eth_rx_burst(port, 0, bufs, BURST_SIZE);

		if (unlikely(nb_rx == 0))
			continue;


		uint16_t buf;
		char* start;
		for (buf = 0; buf < nb_rx; buf++) {
			start = rte_pktmbuf_mtod(bufs[buf], void *); //points to the start of the packet
			int p_len;
			p_len = rte_pktmbuf_pkt_len(bufs[buf]);
			uint16_t p_ether_type;
			memcpy(&p_ether_type, &start[12], 2);
			p_ether_type = ntohs(p_ether_type);

            #ifdef DEBUG
			printf("packet len: %u \n", p_len);
			printf("Ethertype: %04x \n", p_ether_type);
            #endif

		    raw_packet_counter += 1;
			if( (p_ether_type == 0x0800) && (p_len >= 64) ) {
			    uint8_t ihl             = start[14] & 0x0f; //ip header length in 32 bit words
                uint8_t ipv4_protocol   = start[23] & 0xff; //17 = UDP and 6 = TCP
			    uint8_t l4_start        = 14 + ihl*4; // 14 is ethernet header length in bytes

                #ifdef DEBUG
				printf("ihl %02x \n", ihl);
				printf("ipv4_protocol %02x \n", ipv4_protocol);
				printf("l4_start %02x \n", l4_start);
                #endif

			    uint8_t opt_pos = 0;

                uint16_t opt_type;
                uint16_t empty_option_field;

                if (ipv4_protocol == 6) {
			        uint8_t tcp_data_offs   = (start[l4_start + 12] >> 4) & 0x0f; // #tcp header length in in 32 bit words
			        uint8_t tcp_options_len = tcp_data_offs-5; //tcp header always has at least 5x32bit 
                    #ifdef DEBUG
				    printf("tcp_data_offs %02x \n", tcp_data_offs);
				    printf("tcp_options_len %02x \n", tcp_options_len);
                    #endif
			        if (tcp_options_len == 0) continue;

			        //tcp_options     = message[l4_start+ 40 : l4_start+ 40 +tcp_options_len*8]
			        for (uint8_t x = 0; x < tcp_options_len; x++){
				        memcpy(&opt_type, &start[l4_start + 20 + 4*x ], 2);
				        memcpy(&empty_option_field, &start[l4_start + 20 + 4*x + 8 ], 2);
				        opt_type = ntohs(opt_type);
				            if(opt_type == 0x0f10 && empty_option_field == 0x0000) {
					            opt_pos = l4_start + 20 + 4*x;
					            break;
				            }
                        #ifdef DEBUG
				        printf("opt_type %02x \n", opt_type);
				        printf("empty_option_field %02x \n", empty_option_field);
				        printf("opt_pos %04x \n", opt_pos);
                        #endif
                    }
                } else if (ipv4_protocol == 17) {
                    memcpy(&opt_type, &start[l4_start + 8], 2);
                    opt_type = ntohs(opt_type);
                    #ifdef DEBUG
				    printf("PARSED UDP PACKET:\n");
			        printf("opt_type %02x \n", opt_type);
			        printf("empty_option_field %02x \n", empty_option_field);
                    #endif
		            if(opt_type == 0x0f10 && empty_option_field == 0x0000) {
		                opt_pos = l4_start + 8; //UDP header is 64 bit long (8 byte) => 64/8
		            }
                }


			    if(opt_pos != 0) {
				    struct packet_data *p = (struct packet_data*) malloc(sizeof(struct packet_data));
				    memcpy( &(p->t_stamp1), &start[opt_pos+2], 6);
				    memcpy( &(p->t_stamp2), &start[opt_pos+10], 6);
				    p->t_stamp1 = be64toh(p->t_stamp1);
				    p->t_stamp2 = be64toh(p->t_stamp2);
				    p->t_stamp1 = (p->t_stamp1 >> 16) & 0x0000ffffffffffff;
				    p->t_stamp2 = (p->t_stamp2 >> 16) & 0x0000ffffffffffff;

				    if(first == NULL) first = last = p;

					p->packet_sizes = p_len;

				    p->next = NULL;
				    last->next = p;
				    last = p;

                    #ifdef DEBUG
				    printf("tstamp1: 0x%"PRIx64"\n", p->t_stamp1);
				    printf("tstamp2: 0x%"PRIx64"\n", p->t_stamp2);
                    #endif
			    }//else no P4STA option found
		    
			}
		}
		
		for (buf = 0; buf < nb_rx; buf++)
			rte_pktmbuf_free(bufs[buf]);

	}
	//write captured data to csv files:

	char filename[100];
	strcpy(filename, "raw_packet_counter_");
	strcat(filename, fname);
	strcat(filename, ".csv");
	printf(filename);
	printf("\n");

	FILE *raw_pkt_cntr = fopen(filename, "w");
	fprintf(raw_pkt_cntr, "%"PRIu64, raw_packet_counter);
	fclose(raw_pkt_cntr);

	if (first != NULL){
		//create files
		strcpy(filename, "packet_sizes_");
		strcat(filename, fname);
		strcat(filename, ".csv");
		FILE *packet_sizes = fopen(filename, "w");

		strcpy(filename, "timestamp1_list_");
		strcat(filename, fname);
		strcat(filename, ".csv");
		FILE *timestamp1_list = fopen(filename, "w");

		strcpy(filename, "timestamp2_list_");
		strcat(filename, fname);
		strcat(filename, ".csv");
		FILE *timestamp2_list = fopen(filename, "w");

		struct packet_data *iter = first;
		do {
			fprintf(timestamp1_list, "%"PRIu64"\n", iter->t_stamp1);
			fprintf(timestamp2_list, "%"PRIu64"\n", iter->t_stamp2);
			fprintf(packet_sizes, "%"PRIu64"\n", iter->packet_sizes);
			struct packet_data *current = iter;
			iter = iter->next;
			free(current);
		} while(iter != NULL);
		fclose(packet_sizes);
		fclose(timestamp1_list);
		fclose(timestamp2_list);
	}
	status = fopen("receiver_finished.log", "w");
	fprintf(status, "True");
	fclose(status);
}


/*
 * The main function, which does initialization and calls the per-lcore
 * functions.
 */
int main(int argc, char *argv[]) {
	struct rte_mempool *mbuf_pool;
	unsigned nb_ports;
	uint16_t portid;
	portid=0;
	nb_ports = 1; 

	/* Initialize the Environment Abstraction Layer (EAL). */
	int ret = rte_eal_init(argc, argv);
	if (ret < 0)
		rte_exit(EXIT_FAILURE, "Error with EAL initialization\n");

	argc -= ret;
	argv += ret;
	
	printf("argc %u\n", argc);
	if ((argc == 4) && (0 == strcmp( argv[2], "--name")) ) {
        fname = argv[3];
	} else
        fname = "1234";


	/* Creates a new mempool in memory to hold the mbufs. */
	mbuf_pool = rte_pktmbuf_pool_create("MBUF_POOL", NUM_MBUFS * nb_ports,
		MBUF_CACHE_SIZE, 0, RTE_MBUF_DEFAULT_BUF_SIZE, rte_socket_id());

	if (mbuf_pool == NULL)
		rte_exit(EXIT_FAILURE, "Cannot create mbuf pool\n");

	/* Initialize all ports. */
	if (port_init(portid, mbuf_pool) != 0)
		rte_exit(EXIT_FAILURE, "Cannot init port %"PRIu16 "\n", portid);

	if (rte_lcore_count() > 1)
		printf("\nWARNING: Too many lcores enabled. Only 1 used.\n");

	/* Call lcore_main on the master core only. */
	lcore_main();

	return 0;
}
