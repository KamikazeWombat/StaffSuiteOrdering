#use: certbot renew --post-hook /usr/local/bin/certbot-renew-fix-file-access.sh

chmod 0755 /etc/letsencrypt/
chmod 0711 /etc/letsencrypt/live/
chmod 0750 /etc/letsencrypt/live/tet.codewombat.software/
chmod 0711 /etc/letsencrypt/archive/
chmod 0750 /etc/letsencrypt/archive/tet.codewombat.software/
chmod 0640 /etc/letsencrypt/archive/tet.codewombat.software/{cert,chain,fullchain}*.pem
chmod 0640 /etc/letsencrypt/archive/tet.codewombat.software/privkey*.pem

chown root:root /etc/letsencrypt/
chown root:root /etc/letsencrypt/live/
chown root:mail /etc/letsencrypt/live/tet.codewombat.software/
chown root:root /etc/letsencrypt/archive/
chown root:mail /etc/letsencrypt/archive/tet.codewombat.software/
chown root:mail /etc/letsencrypt/archive/tet.codewombat.software/{cert,chain,fullchain}*.pem
chown root:mail /etc/letsencrypt/archive/tet.codewombat.software/privkey*.pem

