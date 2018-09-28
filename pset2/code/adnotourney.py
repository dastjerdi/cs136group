#!/usr/bin/python

# This is a dummy peer that just illustrates the available information your peers
# have available.

# You'll want to copy this file to AgentNameXXX.py for various versions of XXX,
# probably get rid of the silly logging messages, and then add more logic.

import random
import logging

from messages import Upload, Request
from util import even_split
from peer import Peer

class AdnoTourney(Peer):
    def post_init(self):
        print "post_init(): %s here!" % self.id
        self.dummy_state = dict()
        self.dummy_state["cake"] = "lie"
        self.tyrant_rate = {}
        self.last_request = []

    def requests(self, peers, history):
        """
        peers: available info about the peers (who has what pieces)
        history: what's happened so far as far as this peer can see

        returns: a list of Request() objects

        This will be called after update_pieces() with the most recent state.
        """
        needed = lambda i: self.pieces[i] < self.conf.blocks_per_piece
        needed_pieces = filter(needed, range(len(self.pieces)))
        np_set = set(needed_pieces)  # sets support fast intersection ops.


        logging.debug("%s here: still need pieces %s" % (
            self.id, needed_pieces))

        logging.debug("%s still here. Here are some peers:" % self.id)
        for p in peers:
            logging.debug("id: %s, available pieces: %s" % (p.id, p.available_pieces))

        logging.debug("And look, I have my entire history available too:")
        logging.debug("look at the AgentHistory class in history.py for details")
        logging.debug(str(history))

        requests = []   # We'll put all the things we want here
        # Symmetry breaking is good...
        random.shuffle(needed_pieces)

        # Sort peers by id.  This is probably not a useful sort, but other
        # sorts might be useful
        peers.sort(key=lambda p: p.id)
        # request all available pieces from all peers!
        # (up to self.max_requests from each)
        for peer in peers:
            av_set = set(peer.available_pieces)
            isect = av_set.intersection(np_set)
            n = min(self.max_requests, len(isect))
            # More symmetry breaking -- ask for random pieces.
            # This would be the place to try fancier piece-requesting strategies
            # to avoid getting the same thing from multiple peers at a time.
            for piece_id in random.sample(isect, n):
                # aha! The peer has this piece! Request it.
                # which part of the piece do we need next?
                # (must get the next-needed blocks in order)
                start_block = self.pieces[piece_id]
                r = Request(self.id, peer.id, piece_id, start_block)
                requests.append(r)

        return requests

    def uploads(self, requests, peers, history):
        """
        requests -- a list of the requests for this peer for this round
        peers -- available info about all the peers
        history -- history for all previous rounds

        returns: list of Upload objects.

        In each round, this will be called after requests().
        """

        round = history.current_round()
        logging.debug("%s again.  It's round %d." % (
            self.id, round))
        # One could look at other stuff in the history too here.
        # For example, history.downloads[round-1] (if round != 0, of course)
        # has a list of Download objects for each Download to this peer in
        # the previous round.


        if not self.tyrant_rate:
            for peer in peers:
                self.tyrant_rate[peer.id] = [1, self.up_bw / len(peers) , 1]

        if round != 0:
            for trans in history.uploads[round-1]:
                self.tyrant_rate[trans.to_id][0] = trans.bw


            alpha = .31
            gamma = .0079
            non_choke = []
            for trans in history.downloads[round - 1]:
                non_choke.append(trans.from_id)

            peer_reqs = []
            for req in self.last_request:
                peer_reqs.append(req.peer_id)

            for key in self.tyrant_rate:
                if key in non_choke:
                    self.tyrant_rate[key][1] = (1 - gamma)*self.tyrant_rate[key][1]
                elif key in peer_reqs:
                    self.tyrant_rate[key][1] = (1 + alpha)*self.tyrant_rate[key][1]

                self.tyrant_rate[key][2] = self.tyrant_rate[key][0] / self.tyrant_rate[key][1]

        upload_order = sorted(self.tyrant_rate.items(), key=lambda x: x[1][2])
        upload_order = [x[0] for x in upload_order]


        if len(requests) == 0:
            logging.debug("No one wants my pieces!")
            chosen = []
            bws = []
        else:
            logging.debug("Still here: uploading to a random peer")
            
            chosen = []

            remaining_bw = self.up_bw - .001
            request_peers = []
            for req in requests:
                request_peers.append(req.requester_id)

            max_requests = min(4,len(request_peers))

            counter = 0
            for peer in upload_order:
                if counter > 3:
                    break
                if peer in request_peers:
                    chosen += [peer]
                    request_peers.remove(peer)
                    counter += 1
                    print(peer)


            print(len(chosen))
            random_chosen = random.sample(request_peers, max_requests - len(chosen))
            chosen +=  random_chosen
            bws = even_split(self.up_bw, len(chosen))

        # create actual uploads out of the list of peer ids and bandwidths
        uploads = [Upload(self.id, peer_id, bw)
                   for (peer_id, bw) in zip(chosen, bws)]

        return uploads
