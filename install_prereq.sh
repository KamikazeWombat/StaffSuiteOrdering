apt-get install -y python3
apt-get install -y python3-pip
wget https://downloads.wkhtmltopdf.org/0.12/0.12.5/wkhtmltox_0.12.5-1.bionic_amd64.deb
sudo apt install -y ./wkhtmltox_0.12.5-1.bionic_amd64.deb
pip3 install cherrypy
pip3 install python-dateutil
pip3 install jinja2
pip3 install requests
pip3 install pdfkit
pip3 install sqlalchemy
git clone https://github.com/KamikazeWombat/StaffSuiteOrdering
apt-get update
apt-get install software-properties-common
add-apt-repository universe
add-apt-repository ppa:certbot/certbot
apt-get update
certbot certonly --standalone