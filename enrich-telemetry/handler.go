package function

import (
	"encoding/json"
	"io"
	"log"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"sync"

	"github.com/oschwald/geoip2-golang"
)

// databases are opened once and reused across invocations.
var (
	cityDB  *geoip2.Reader
	asnDB   *geoip2.Reader
	once    sync.Once
	initErr error
)

func dbDir() string {
	// The OpenFaaS watchdog sets the working directory to the handler folder,
	// which contains the embedded "static/" sub-directory.
	dir, _ := filepath.Abs("static")
	if _, err := os.Stat(dir); err == nil {
		return dir
	}
	return filepath.Join(filepath.Dir(os.Args[0]), "static")
}

func initDBs() {
	once.Do(func() {
		dir := dbDir()
		var err error
		cityDB, err = geoip2.Open(filepath.Join(dir, "GeoLite2-City.mmdb"))
		if err != nil {
			initErr = err
			log.Printf("ERROR opening GeoLite2-City.mmdb: %v", err)
			return
		}
		asnDB, err = geoip2.Open(filepath.Join(dir, "GeoLite2-ASN.mmdb"))
		if err != nil {
			initErr = err
			log.Printf("ERROR opening GeoLite2-ASN.mmdb: %v", err)
		}
	})
}

// enrichEvent adds geo fields to a generic event map. The map is modified
// in-place and returned. The "ip" field must be present.
func enrichEvent(ev map[string]any) map[string]any {
	ipStr, _ := ev["ip"].(string)
	ip := net.ParseIP(ipStr)
	if ip == nil {
		return ev
	}

	if cityDB != nil {
		if rec, err := cityDB.City(ip); err == nil {
			ev["country_code"] = rec.Country.IsoCode
			if name, ok := rec.Country.Names["en"]; ok {
				ev["country_name"] = name
			}
			if name, ok := rec.City.Names["en"]; ok {
				ev["city"] = name
			}
			ev["latitude"] = rec.Location.Latitude
			ev["longitude"] = rec.Location.Longitude
		} else {
			log.Printf("WARN city lookup for %s: %v", ipStr, err)
		}
	}

	if asnDB != nil {
		if rec, err := asnDB.ASN(ip); err == nil {
			ev["asn"] = rec.AutonomousSystemNumber
			ev["asn_org"] = rec.AutonomousSystemOrganization
		} else {
			log.Printf("WARN ASN lookup for %s: %v", ipStr, err)
		}
	}

	return ev
}

// Handle is the OpenFaaS entry point.
// Accepts a JSON object or JSON array of objects, each with an "ip" field.
// Returns the same structure with geo enrichment fields added.
func Handle(w http.ResponseWriter, r *http.Request) {
	initDBs()

	if initErr != nil {
		http.Error(w, "geo database unavailable: "+initErr.Error(), http.StatusInternalServerError)
		return
	}

	defer r.Body.Close()
	body, err := io.ReadAll(r.Body)
	if err != nil {
		http.Error(w, "failed to read body", http.StatusBadRequest)
		return
	}

	w.Header().Set("Content-Type", "application/json")

	// Try array first, then single object, to decide output shape.
	var events []map[string]any
	if err := json.Unmarshal(body, &events); err == nil {
		for i := range events {
			events[i] = enrichEvent(events[i])
		}
		_ = json.NewEncoder(w).Encode(events)
		return
	}

	var single map[string]any
	if err := json.Unmarshal(body, &single); err != nil {
		http.Error(w, "body must be a JSON object or array of objects", http.StatusBadRequest)
		return
	}
	_ = json.NewEncoder(w).Encode(enrichEvent(single))
}
