#!/usr/bin/env python3
"""
Direct test of table extraction from Arkansas page
"""
from utils.text_cleaner import clean_html

# Sample Arkansas table HTML
HTML_SAMPLE = """
<table>
<thead>
<tr style="background-color: #ced4d9;">
<td style="border-image: initial;"><span style="color: #000000;"><span style="font-size: 18px;">&nbsp;</span></span></td>
<td><strong><span style="color: #000000;"><span style="font-size: 18px;">Residence Hall</span></span></strong></td>
<td><strong><span style="color: #000000;"><span style="font-size: 18px;">Off Campus</span></span></strong></td>
<td><strong><span style="color: #000000;"><span style="font-size: 18px;">With Parent</span></span></strong></td>
<td><strong><span style="color: #000000;"><span style="font-size: 18px;">Graduate*</span></span></strong></td>
</tr>
</thead>
<tbody>
<tr>
<td style="background-color: #ced4d9;"><strong><span style="color: #000000;"><span style="font-size: 18px;">Tuition &amp; Fees</span></span></strong></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">10,430</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">10,430</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;"><span>10,430</span></span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">7,556</span></span></td>
</tr>
<tr>
<td style="background-color: #ced4d9;"><strong><span style="color: #000000;"><span style="font-size: 18px;">Books</span></span></strong></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">1,250</span></span></td>
<td><p><span style="color: #000000;"><span>1,250</span><span></span></span></p></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">1,250</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">1,250</span></span></td>
</tr>
<tr>
<td style="background-color: #ced4d9;"><strong><span style="color: #000000;"><span style="font-size: 18px;">Room &amp; Board</span></span></strong></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">11,950</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">11,925</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;"><span>2,720</span></span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">13,190</span></span></td>
</tr>
<tr>
<td style="background-color: #ced4d9;"><strong><span style="color: #000000;"><span style="font-size: 18px;">Personal</span></span></strong></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">2,790</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">2,790</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">2,790</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">2,790</span></span></td>
</tr>
<tr>
<td style="background-color: #ced4d9;"><strong><span style="color: #000000;"><span style="font-size: 18px;">Transportation</span></span></strong></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">3,570</span></span></td>
<td><p><span>5,406</span><span></span></p></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">5,406</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">3,570</span></span></td>
</tr>
<tr>
<td style="background-color: #ced4d9;"><strong><span style="color: #000000;"><span style="font-size: 18px;">Total</span></span></strong></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">29,990</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">31,801</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">22,596</span></span></td>
<td><span style="color: #000000;"><span style="font-size: 18px;">28,356</span></span></td>
</tr>
</tbody>
</table>
<p><span style="color: #000000;"><br><strong>Graduate Non-Residents</strong> Add: $5,922</span></p>
"""

def test_table_extraction():
    print("=" * 80)
    print("TESTING TABLE EXTRACTION")
    print("=" * 80)
    
    cleaned = clean_html(HTML_SAMPLE)
    
    print("\n=== CLEANED TEXT ===\n")
    print(cleaned)
    print("\n" + "=" * 80)
    
    # Check if Graduate column values are present
    graduate_values = ["7,556", "1,250", "13,190", "2,790", "3,570", "28,356"]
    print("\n=== VALIDATION ===\n")
    for val in graduate_values:
        if val in cleaned:
            print(f"✅ {val} found")
        else:
            print(f"❌ {val} NOT FOUND")
    
    if "Graduate*" in cleaned:
        print("✅ Graduate column header found")
    else:
        print("❌ Graduate column header NOT FOUND")
    
    if "|" in cleaned:
        print("✅ Table structure (pipes) preserved")
    else:
        print("❌ Table structure NOT preserved")

if __name__ == "__main__":
    test_table_extraction()
