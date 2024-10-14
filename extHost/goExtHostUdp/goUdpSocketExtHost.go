package main

import (
	"bytes"
	"encoding/binary"
	"encoding/csv"
	"flag"
	"fmt"
	"net"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
	"time"
)

// arrays/slices for csv generation
var timestamp1_list []uint64
var timestamp2_list []uint64
var packet_size_list []uint16
var packet_counter uint64

var name *string
var save *bool
var start_time time.Time

func write_csv_uint_list(filename string, to_write []uint64) {
	file, err := os.Create(fmt.Sprintf("%s_%s.csv", filename, *name))
	if err != nil {
		fmt.Println(err)
	}
	w := csv.NewWriter(file)
	for i := 0; i < len(to_write); i++ {
		var tmp [1]string
		tmp[0] = strconv.FormatUint(to_write[i], 10)
		if err := w.Write(tmp[0:1]); err != nil {
			fmt.Println(err)
		}
		w.Flush()
		if w.Error() != nil {
			fmt.Println(err)
		}

	}
}

func overwrite_textfile(full_filename string, to_write string) {
	// Create() truncates if file already exists => overwrite
	f, err := os.Create(full_filename)
	if err != nil {
		fmt.Println(err)
	} else {
		f.WriteString(to_write)
	}
	if err := f.Close(); err != nil {
		fmt.Println(err)
	}
}

func save_data() {
	fmt.Println("saving data ..")
	fmt.Println("timestamp1 list length: ", len(timestamp1_list))
	fmt.Println("timestamp2 list length: ", len(timestamp2_list))
	fmt.Println("packet_size_list list length: ", len(packet_size_list))
	fmt.Println("packet_counter: ", packet_counter)

	if *save {
		file, err := os.Create(fmt.Sprintf("raw_packet_counter_%s.csv", *name))
		if err != nil {
			panic(err)
		}
		w := csv.NewWriter(file)
		var tmp [1]string
		tmp[0] = strconv.FormatUint(packet_counter, 10)
		if err := w.Write(tmp[0:1]); err != nil {
			fmt.Println(err)
		}
		w.Flush()
		if w.Error() != nil {
			fmt.Println(err)
		}

		write_csv_uint_list("timestamp1_list", timestamp1_list)
		write_csv_uint_list("timestamp2_list", timestamp2_list)

		var packet_size_list_64 []uint64
		for i := 0; i < len(packet_size_list); i++ {
			packet_size_list_64 = append(packet_size_list_64, uint64(packet_size_list[i]))
		}
		write_csv_uint_list("packet_sizes", packet_size_list_64)

		overwrite_textfile("receiver_finished.log", "True")
		fmt.Println("Finished writing")
	}
}

func main() {
	// in extHostHTTPServer, use "go run extHostHTTPServer.go goUdpSocketExtHost.go"
	go start_api()

	start_time = time.Now()

	overwrite_textfile("receiver_finished.log", "False")
	overwrite_textfile("golangUdpSocketExtHost.log", "Started\n")

	// signals handler for SIGTERM and SIGINT
	c := make(chan os.Signal)
	signal.Notify(c, os.Interrupt, syscall.SIGTERM)
	signal.Notify(c, os.Interrupt, syscall.SIGINT)
	go func() {
		<-c
		save_data()
		stop_api()
		fmt.Println("GoLang Ext Host was running for ", time.Since(start_time), " seconds")
		os.Exit(0) //success
	}()

	// create and parse flags from bash call
	name = flag.String("name", "no_name", "Name of generated files => test identification.")
	var ip_port = flag.String("ip_port", "0.0.0.0:41111", "IP the UDP sockets binds to.")
	var ip = flag.String("ip", "0.0.0.0", "IP the IP socket binds to")
	save = flag.Bool("save", true, "(Default true): If set to false, no csv files will be stored after sniffing")
	flag.Parse()

	fmt.Println("name has value", *name)
	fmt.Println("ip_port has value", *ip_port)
	fmt.Println("ip has value", *ip)

	udp_addr, err := net.ResolveUDPAddr("udp", strings.ReplaceAll(*ip_port, " ", ""))

	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	// Start listening for UDP packages on the given address
	conn, err := net.ListenUDP("udp", udp_addr)

	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	var paket_len_original uint16
	var timestamp1 uint64
	var timestamp2 uint64

	var padding = []byte{0, 0} // to fill 6 byte timestamp into uint64

	packet_counter = 0

	// Read from UDP listener in endless loop
	for {
		var buf [100]byte
		_, _, err := conn.ReadFromUDP(buf[0:]) //_, addr
		if err != nil {
			fmt.Println(err)
			overwrite_textfile("golangUdpSocketExtHost.log", err.Error())
			return
		}

		packet_counter = packet_counter + 1

		// indicates p4sta timestamp starting with 0x0f10, the 2 prior bytes are ext host statistics header, parsed also now.
		// if binary.BigEndian.Uint16(buf[2:4]) == 0x0f10 {   => TODO: dont know which is faster, conversion to Uint or bytes.Equal
		if bytes.Equal([]byte{0x0f, 0x10}, buf[2:4]) {
			paket_len_original = binary.BigEndian.Uint16(buf[0:2])
			timestamp1 = binary.BigEndian.Uint64(append(padding, buf[4:10]...))
			// empty .. buf[10:12]
			timestamp2 = binary.BigEndian.Uint64(append(padding, buf[12:18]...))

			timestamp1_list = append(timestamp1_list, timestamp1)
			timestamp2_list = append(timestamp2_list, timestamp2)
			packet_size_list = append(packet_size_list, paket_len_original)
		}
	}
}
