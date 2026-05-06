package zilliz

import (
	"encoding/json"
	"testing"
)

func TestParseSearchHitsFlatResponse(t *testing.T) {
	data := json.RawMessage(`[
		{"distance":0.91,"text":"flat memory","source":"flat-source"},
		{"distance":0.82,"entity":{"text":"entity memory","source":"entity-source"}}
	]`)

	hits, err := parseSearchHits(data)
	if err != nil {
		t.Fatalf("parseSearchHits() error = %v", err)
	}
	if len(hits) != 2 {
		t.Fatalf("len(hits) = %d, want 2", len(hits))
	}
	if hits[0].Text != "flat memory" || hits[0].Source != "flat-source" || hits[0].Score != 0.91 {
		t.Fatalf("hits[0] = %+v", hits[0])
	}
	if hits[1].Text != "entity memory" || hits[1].Source != "entity-source" || hits[1].Score != 0.82 {
		t.Fatalf("hits[1] = %+v", hits[1])
	}
}

func TestParseSearchHitsNestedResponse(t *testing.T) {
	data := json.RawMessage(`[
		[
			{"distance":0.77,"entity":{"text":"nested memory","source":"nested-source"}}
		]
	]`)

	hits, err := parseSearchHits(data)
	if err != nil {
		t.Fatalf("parseSearchHits() error = %v", err)
	}
	if len(hits) != 1 {
		t.Fatalf("len(hits) = %d, want 1", len(hits))
	}
	if hits[0].Text != "nested memory" || hits[0].Source != "nested-source" || hits[0].Score != 0.77 {
		t.Fatalf("hits[0] = %+v", hits[0])
	}
}

func TestParseSearchHitsWrappedResponse(t *testing.T) {
	data := json.RawMessage(`{
		"results": [
			{"distance":0.66,"text":"wrapped memory","source":"wrapped-source"}
		]
	}`)

	hits, err := parseSearchHits(data)
	if err != nil {
		t.Fatalf("parseSearchHits() error = %v", err)
	}
	if len(hits) != 1 {
		t.Fatalf("len(hits) = %d, want 1", len(hits))
	}
	if hits[0].Text != "wrapped memory" || hits[0].Source != "wrapped-source" || hits[0].Score != 0.66 {
		t.Fatalf("hits[0] = %+v", hits[0])
	}
}
