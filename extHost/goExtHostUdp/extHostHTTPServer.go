// Little debugging HTTP server to see if ext host is still processing packets

package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

var seqno uint64
var server *http.Server

type read_results_message struct {
	Id             uint64   `json:"id"`
	PacketCounter  uint64   `json:"packetcounter"`
	Timestamp1List []uint64 `json:"timestamp1list"`
	Timestamp2List []uint64 `json:"timestamp2list"`
}

type run_state_message struct {
	RunState  string    `json:"current_run_state"`
	StartTime time.Time `json:"start_time"`
}

func readResultsHandler(w http.ResponseWriter, r *http.Request) {

	switch r.Method {
	case "GET":
		var m *read_results_message = &read_results_message{
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
	}
}

func runStateHandler(w http.ResponseWriter, r *http.Request) {

	switch r.Method {
	case "GET":
		var m *run_state_message = &run_state_message{
			RunState:  current_run_state,
			StartTime: start_time,
		}

		j, _ := json.Marshal(m)
		w.Write(j)
	default:
		w.WriteHeader(http.StatusMethodNotAllowed)
	}
}

func start_api() {
	fmt.Println("Start HTTP Server at Port 8888")

	server = &http.Server{
		Addr: ":8888",
	}

	seqno = 0
	http.HandleFunc("/results", readResultsHandler)
	http.HandleFunc("/run_state", runStateHandler)

	fmt.Println("Start HTTP API")
	server.ListenAndServe()

	fmt.Println("End HTTP Server")
}

func stop_api() {
	server.Close()
}
