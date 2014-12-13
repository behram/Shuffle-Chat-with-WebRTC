Shuffle Chat with WebRTC
==================================
Overview
------------
Shuffle Chat App is an shuffle video chat app coded with Python and runs in Google App Engine. Project implemented from [WebRTC demos and samples](https://github.com/GoogleChrome/webrtc) and edited for shuffle video chat and api for Android App. Developed by [Deepkod Freelance Group](http://www.deepkod.com). Runs in [shufflechat.me](https://shufflechat.me)

 - Demo Site => https://shufflechat.me
 
 
Install
------------
For preparing we are installing some packages ( nodejs | npm | Google App Engine ).

		sudo apt-get upgrade
		sudo apt-get update
		sudo apt-get install nodejs
		sudo apt-get install unzip
		sudo apt-get install apache2
		curl https://npmjs.org/install.sh | sudo sh
		cd ~
		wget https://storage.googleapis.com/appengine-sdks/featured/google_appengine_1.9.17.zip
		unzip google_appengine_1.9.17.zip
		
Clone repo

	git clone https://github.com/deepkod/Shuffle-Chat-with-WebRTC.git
	cd ./Shuffle-Chat-with-WebRTC

Edit basic settings 
	
	nano ./samples/web/content/apprtc/apprtc.py
and replace all shufflechat.me urls with localhost.

Apache Proxy
-----------------
We must run program on https url because off permission problems ( [reason](https://support.google.com/chrome/answer/2693767?hl=en) ) . We will use apache2 as a local proxy server.

This steps can be a little advanced if you got trouble contact with us.
Email : deepkod@gmail.com
Site Contact :  http://www.deepkod.com/#contact
Or open a issue

For use local ssl Certificate please apply this beautiful [article](https://www.digitalocean.com/community/tutorials/how-to-create-a-ssl-certificate-on-apache-for-ubuntu-14-04).

For use apache as proxy bridge apply this crazy [article](https://www.digitalocean.com/community/tutorials/how-to-use-apache-http-server-as-reverse-proxy-using-mod_proxy-extension).
Addition to article : We will use https because of that you must change /etc/apache2/sites-available/default-ssl.conf not /etc/apache2/sites-enabled/000-default.conf file.
Proxy addresses in article use as below: 

	ProxyPass / http://localhost:8080/
    ProxyPassReverse / http://localhost:8080/
Lets run our perfect app.
	
	cd ~
	chmod +x local_run.sh
	./local_run.sh
And open with your browser https://localhost. If everything is works you must see an certification warning say ok i am trusting my app. ( On production you must get a real certificate ). Have Fun with Random Video Chat boy. 
		
Referances
------------------
 - https://shufflechat.me
 - http://www.webrtc.org/
 - https://github.com/GoogleChrome/webrtc
 - http://www.html5rocks.com/en/tutorials/webrtc/basics/
 - https://apprtc.appspot.com
 - https://cloud.google.com/appengine/docs/python/
 - https://www.digitalocean.com/community/tutorials/how-to-create-a-ssl-certificate-on-apache-for-ubuntu-14-04
 - https://www.digitalocean.com/community/tutorials/how-to-use-apache-http-server-as-reverse-proxy-using-mod_proxy-extension

Contact
---------
Email us : [deepkod@gmail.com](mailto:deepkod@gmail.com) | [deepkod@deepkod.com](mailto:deepkod@deepkod.com)
Contact us : http://www.deepkod.com/#contact
Or open an issue

We will wait for your pull requests all time bros :D Have Good time
