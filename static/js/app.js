var app = new Vue({
  el: '#app',
  data: {
    searchTerms: '',
    hits: [],
    new_depicts: [],
  },
  methods: {
    add_depicts(hit) {
      this.new_depicts.push(hit);
      this.hits = [];
      this.searchTerms = '';
    },
    search(event) {
      var terms = this.searchTerms;
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
    }
  },
});
