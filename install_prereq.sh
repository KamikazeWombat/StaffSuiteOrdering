apt-get install -y python3
apt-get install -y python3-pip
wget https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6-1/wkhtmltox_0.12.6-1.buster_amd64.deb
sudo apt install -y ./wkhtmltox_0.12.6-1.buster_amd64.deb
pip3 install cherrypy
pip3 install python-dateutil
pip3 install jinja2
pip3 install requests
pip3 install pdfkit
pip3 install sqlalchemy
apt-get update
sudo apt install -y certbot
apt-get install software-properties-common
add-apt-repository universe
add-apt-repository ppa:certbot/certbot
apt-get update
certbot certonly --standalone