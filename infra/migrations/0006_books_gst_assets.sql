-- Books: an optional GST rate on a cash-book line (the amount includes the tax) and, for the sale of an asset, its book value so the profit or loss on sale can be worked out.
ALTER TABLE se_entries ADD COLUMN gst_rate NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (gst_rate >= 0 AND gst_rate <= 28);
ALTER TABLE se_entries ADD COLUMN book_value NUMERIC(15,2) CHECK (book_value IS NULL OR book_value >= 0);
