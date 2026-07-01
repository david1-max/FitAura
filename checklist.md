# SEO & Google Search Deployment Checklist

Follow this checklist once you deploy the FitAura website to PythonAnywhere to ensure Google indexes your site and ranks your products near the top of search results.

---

## 1. Register with Google Search Console
- [ ] Go to [Google Search Console](https://search.google.com/search-console/about).
- [ ] Add your live site URL (e.g., `https://yourusername.pythonanywhere.com`).
- [ ] Verify ownership by pasting Google's verification `<meta>` tag into the `<head>` of your `index.html` template.
- [ ] Click **Request Indexing** to submit your site homepage for crawling.

---

## 2. Dynamic Sitemap Integration (FastAPI)
- [ ] Implement a `GET /sitemap.xml` route in the FastAPI backend (`main.py`).
- [ ] Query the database for all active product slugs.
- [ ] Format the list of URLs using the standard XML sitemap layout:
  ```xml
  <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://yourdomain.com/</loc><changefreq>daily</changefreq></url>
    <url><loc>https://yourdomain.com/shop.html</loc><changefreq>daily</changefreq></url>
    <!-- Add products dynamically from SQLite here -->
  </urlset>
  ```
- [ ] Submit your sitemap link (`https://yourdomain.com/sitemap.xml`) inside the **Sitemaps** section of Google Search Console.

---

## 3. Structured Product Schema (Rich Snippets)
- [ ] Embed JSON-LD product data inside [product.html](file:///C:/Users/USER/Documents/antigravity/happy-rutherford/FitAura/static/product.html) dynamically using Javascript:
  ```html
  <script type="application/ld+json" id="schemaProduct"></script>
  ```
- [ ] Format JSON data on load:
  ```javascript
  const schema = {
    "@context": "https://schema.org/",
    "@type": "Product",
    "name": p.name,
    "image": window.location.origin + p.image_url,
    "description": "Premium streetwear from FitAura.",
    "offers": {
      "@type": "Offer",
      "price": p.price,
      "priceCurrency": "INR",
      "availability": p.stock > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock"
    }
  }
  document.getElementById('schemaProduct').textContent = JSON.stringify(schema);
  ```
- [ ] Verify using Google's [Rich Results Test](https://search.google.com/test/rich-results) tool to display price, ratings, and stock status directly on Google Search cards.

---

## 4. Target Localized Keywords
- [ ] Optimize page titles in HTML files. Replace generic titles with descriptive long-tail terms:
  - *Current:* `<title>FitAura</title>`
  - *Recommended:* `<title>FitAura | Premium Oversized Streetwear & Hoodies India</title>`
- [ ] Write rich product description text on the storefront containing search terms like "Heavyweight Cotton T-shirt", "Drop Shoulder Hoodies", and "Aesthetic Clothing".

---

## 5. Google Business Profile & Backlinks
- [ ] Create a free **Google Business Profile** listing your storefront brand.
- [ ] Link your store URL on social media bios (Instagram, TikTok, YouTube).
- [ ] Encourage backlinks from blogs and fashion catalogs to boost domain authority rankings.
