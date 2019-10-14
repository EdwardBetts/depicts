var typingTimer;
var doneTypingInterval = 500;

var app = new Vue({
    el: '#app',
    delimiters: ['${', '}'],
    data: {
        prevTerms: {},
        searchTerms: {},
        hits: {},
    },
    methods: {
        run_search(qid) {
            var terms = this.searchTerms[qid];
            if (terms == this.prevTerms[qid]) {
                return;  // no change
            }
            this.prevTerms[qid] = terms;
            if (terms.length < 3) {
                this.hits[qid] = [];
                return;
            }

            var vm = this;

            fetch(lookup_url + '?terms=' + encodeURI(terms))
                .then((res) => res.json())
                .then((data) => {
                    vm.hits[qid] = data.hits;
                })
        },
        search(event) {
            var qid = event.target.dataset.qid
            clearTimeout(typingTimer);
            typingTimer = setTimeout(this.run_search, doneTypingInterval, qid);
        }
    }
});
