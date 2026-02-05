package main

import "strings"

func classifyJob(job JobRecord, requireLocation, requireProduction bool) string {
	text := strings.ToLower(strings.TrimSpace(strings.Join([]string{
		job.Title, job.Company, job.Location, job.Description,
	}, " ")))

	tokens := tokenize(text)

	aiTokens := []string{"ai", "ml", "llm", "nlp", "rag", "genai"}
	aiPhrases := []string{"machine learning", "artificial intelligence", "deep learning", "computer vision"}
	pythonTokens := []string{"python", "pytorch", "tensorflow", "scikit", "sklearn", "keras"}
	prodTokens := []string{"production", "deploy", "deployment", "ci", "cd", "kubernetes", "docker", "pipeline", "scalable", "scalability", "cloud", "monitoring"}
	dealPhrases := []string{"front-end", "frontend", "react", "angular", "ios", "android", "qa", "tester", "sdet", "support", "help desk", "marketing", "sales", "recruiter", "wordpress", "designer"}
	sapTokens := []string{"sap", "abap", "dotnet", "csharp", "c#", "vb"}
	sapPhrases := []string{".net"}

	hasAI := containsToken(tokens, aiTokens) || containsPhrase(text, aiPhrases)
	hasPython := containsToken(tokens, pythonTokens)
	hasProduction := containsToken(tokens, prodTokens)
	hasDealbreaker := containsPhrase(text, dealPhrases)
	hasSAP := containsToken(tokens, sapTokens) || containsPhrase(text, sapPhrases)

	if !hasAI {
		if hasDealbreaker || hasSAP {
			return "reject"
		}
		return "reject"
	}

	if requireProduction && !hasProduction {
		return "reviewed"
	}
	if !hasPython {
		return "reviewed"
	}

	locationOK := locationPreferred(job.Location)
	if requireLocation && !locationOK {
		return "reviewed"
	}

	return "shortlist"
}

func tokenize(text string) map[string]struct{} {
	var b strings.Builder
	for _, r := range text {
		if (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') {
			b.WriteRune(r)
		} else {
			b.WriteRune(' ')
		}
	}
	words := strings.Fields(b.String())
	out := make(map[string]struct{}, len(words))
	for _, w := range words {
		out[w] = struct{}{}
	}
	return out
}

func containsToken(tokens map[string]struct{}, keywords []string) bool {
	for _, k := range keywords {
		if _, ok := tokens[k]; ok {
			return true
		}
	}
	return false
}

func containsPhrase(text string, phrases []string) bool {
	for _, p := range phrases {
		if strings.Contains(text, p) {
			return true
		}
	}
	return false
}

func locationPreferred(location string) bool {
	loc := strings.ToLower(location)
	if loc == "" {
		return false
	}
	preferred := []string{"ontario", "toronto", "ottawa", "waterloo", "gta", "canada", "remote"}
	for _, token := range preferred {
		if strings.Contains(loc, token) {
			return true
		}
	}
	return false
}
