import polars as pl, glob, collections, random, re
RAW="../data/raw/c0b3a9190fd970e83cfbe7d399a08860e43e221e/data"
df=pl.read_parquet(sorted(glob.glob(f"{RAW}/test-*.parquet"))).filter(pl.col("questions_count")>0)
ex=df.select("path","email","questions","gold_answers","alternate_answers","incorrect_answers").explode(["questions","gold_answers","alternate_answers","incorrect_answers"])
qs=ex["questions"].to_list(); golds=ex["gold_answers"].to_list(); ems=ex["email"].to_list()
fw=collections.Counter(q.split()[0].lower().strip('",') for q in qs)
print("first word", fw.most_common(20))
# gold verbatim in email?
def norm(s): return re.sub(r'\s+',' ',s.lower())
verb=sum(1 for g,e in zip(golds,ems) if norm(g.rstrip('.')) in norm(e))
print("gold (minus trailing period) verbatim in email:", verb, "of", len(golds))
# yes/no
yn=sum(1 for g in golds if re.match(r'^(yes|no)\b',g.strip(),re.I)); print("gold starts yes/no", yn)
# gold contains digit
print("gold has digit", sum(1 for g in golds if re.search(r'\d',g)))
random.seed(7)
for i in random.sample(range(len(qs)),15): print("Q:",qs[i],"\n   G:",golds[i],"\n   ALT:",ex["alternate_answers"][i][0],"\n   BAD:",ex["incorrect_answers"][i][0],"\n")
