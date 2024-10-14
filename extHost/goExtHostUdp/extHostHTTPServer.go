// Little debugging HTTP server to see if ext host is still processing packets

package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
)

var seqno uint64

type message struct {
	Id             uint64   `json:"id"`
	PacketCounter  uint64   `json:"packetcounter"`
	Timestamp1List []uint64 `json:"timestamp1list"`
	Timestamp2List []uint64 `json:"timestamp2list"`
}

func callHandler(w http.ResponseWriter, r *http.Request) {

	switch r.Method {
	case "GET":
		var m *message = &message{
			Id:             seqno,
			PacketCounter:  packet_counter,
			Timestamp1List: timestamp1_list,
			Timestamp2List: timestamp2_list,
		}

		j, _ := json.Marshal(m)
		w.Write(j)

		seqno = seqno + 1
	// case "POST":
	// 	// Decode the JSON in the body and overwrite message with it
	// 	d := json.NewDecoder(r.Body)
	// 	p := &message{}
	// 	err := d.Decode(p)
	// 	if err != nil {
	// 		http.Error(w, err.Error(), http.StatusInternalServerError)
	// 	}
	// 	m1 = p
	default:
		w.WriteHeader(http.StatusMethodNotAllowed)
		fmt.Fprintf(w, "I can't do that.")
	}
}

func start_api() {
	log.Println("Start HTTP Server at Port 8080")

	seqno = 0
	http.HandleFunc("/state", callHandler)

	log.Println("Start HTTP API")
	http.ListenAndServe("0.0.0.0:8888", nil)

	log.Println("End HTTP Server")
}

func stop_api() {
	// http.Shutdown()
}
