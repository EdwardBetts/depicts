var typingTimer;
var doneTypingInterval = 500;

var app = new Vue({
    el: '#app',
    data: {
        prevTerms: '',
        searchTerms: '',
        hits: [],
        new_depicts: [],
        existing_depicts: existing_depicts,
    },
    methods: {
        remove(index) {
            this.$delete(this.new_depicts, index);
        },
        add_depicts(hit) {
            this.new_depicts.push(hit);
            this.hits = [];
            this.searchTerms = '';
        },
        run_search() {
            var terms = this.searchTerms;
            if (terms == this.prevTerms) {
                return;  // no change
            }
            this.prevTerms = terms;
            if (terms.length < 3) {
                this.hits = [];
                return;
            }

            var vm = this;

            fetch(lookup_url + '?terms=' + encodeURI(terms))
                .then((res) => res.json())
                .then((data) => {
                    vm.hits = data.hits;
                })
        },
        search(event) {
            clearTimeout(typingTimer);
            typingTimer = setTimeout(this.run_search, doneTypingInterval);
        }
    },
});
