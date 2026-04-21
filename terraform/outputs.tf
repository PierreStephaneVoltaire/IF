# Nameservers assigned by Cloudflare for each managed zone.
# After the first apply, copy these values into Namecheap:
#   Domain List → Manage → Nameservers → Custom DNS → paste both NS values.
output "cloudflare_nameservers" {
  description = "Cloudflare nameservers per zone — update these at Namecheap after first apply"
  value = {
    for zone, resource in cloudflare_zone.managed :
    zone => resource.name_servers
  }
}

output "cloudflare_tunnel_id" {
  description = "Tunnel ID (used in CNAME targets: <id>.cfargotunnel.com)"
  value       = cloudflare_zero_trust_tunnel_cloudflared.this.id
}
