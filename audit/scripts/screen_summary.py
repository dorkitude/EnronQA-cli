import polars as pl, sys, json
sys.path.insert(0, "scripts"); from common import questions, LEDGER
q = questions().select("qid","split","user","include_email").join(pl.read_parquet(LEDGER/"screen.parquet"), on="qid")
def pct(df, col): 
    g = df.group_by("split").agg(pl.col(col).mean().alias("rate"), pl.col(col).sum().alias("n")).sort("split")
    return {r["split"]: {"n": int(r["n"]), "pct": round(100*r["rate"],1)} for r in g.to_dicts()}
out={}
for c in ["gold_yes_no","gold_date_textual","gold_date_numeric","gold_time","gold_money","gold_percent","gold_email_addr","gold_url","gold_phone","gold_quote","gold_hedge","gold_verbatim_in_email","alt_verbatim_in_email","gold_numbers_all_in_email","q_according","q_multi_wh","inc_hedge_any","inc_anachronism_any","inc_shares_gold_numbers_any","inc_any_in_email_lcs_gt_half","alt_equals_gold"]:
    out[c]=pct(q,c)
out["q_type"]=q.group_by("split","q_type").len().pivot(on="split",index="q_type",values="len").fill_null(0).sort("q_type").to_dicts()
out["gold_number_count_dist"]=q.group_by("gold_number_count").len().sort("gold_number_count").head(8).to_dicts()
out["gold_lcs_ratio_quantiles"]={str(p): round(q["gold_lcs_ratio"].quantile(p),3) for p in [0.1,0.25,0.5,0.75,0.9]}
out["gold_lcs_ratio_ge_0.8"]=pct(q.with_columns((pl.col("gold_lcs_ratio")>=0.8).alias("x")),"x")
out["gold_words_quantiles"]={str(p): q["gold_words"].quantile(p) for p in [0.1,0.5,0.9,0.99]}
out["gold_numbers_missing_from_email_gt0"]=pct(q.with_columns((pl.col("gold_numbers_missing_from_email")>0).alias("x")),"x")
out["gold_caps_in_email_ratio_lt_0.5"]=pct(q.with_columns((pl.col("gold_caps_in_email_ratio")<0.5).alias("x")),"x")
out["inc_words_mean_minus_gold_words_quantiles"]={str(p): round(q.with_columns((pl.col("inc_words_mean")-pl.col("gold_words")).alias("d"))["d"].quantile(p),1) for p in [0.1,0.5,0.9]}
json.dump(out, open(LEDGER.parent/"report"/"screen_summary.json","w"), indent=1, default=str)
print(json.dumps(out, indent=1, default=str)[:6000])
