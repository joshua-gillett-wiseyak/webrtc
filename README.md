# How Signaling Server Works:
1 - Peer 1(Offerer) - creates an offer, sends to signaling server

	1-Creates offer
	
	2-Sets Local Description
	
2 - Peer2 2(Answerer) - Requests for an offer, create an Answer

	1-Sets Remote Description
	
	2-Creates Answer
	
	3-Sets Local Description
	
3 - Peer 2(Answerer) - Sends the Answer to signaling server

4 - Peer 1(Offerer) - Receives the Answer

	3-Sets Remote Description

# Steps to run:
>
> pip install requirements.txt
>
> python server.py
>
> Run: 
> python client.py
>
<!-- > After Recording has been completed, run: python answerer.py -->
>
	