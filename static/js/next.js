var app = new Vue({
    el: '#app',
    data: {
        other_props: other_props,
    },
    created() {
        this.other_props.forEach((prop) => {
            var url = prop.image_lookup;

            fetch(url)
                .then((res) => res.json())
                .then((data) => { prop.images = data.items; })
        });
    }
});
