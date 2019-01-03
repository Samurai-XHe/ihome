function hrefBack() {
    history.go(-1);
}

function decodeQuery(){
    var search = decodeURI(document.location.search);
    return search.replace(/(^\?)/, '').split('&').reduce(function(result, item){
        values = item.split('=');
        result[values[0]] = values[1];
        return result;
    }, {});
}

$(function(){
    // ��ȡ����ҳ��Ҫչʾ�ķ��ݱ��
    var queryData = decodeQuery();
    var houseId = queryData["id"];

    // ��ȡ���ݵ���ϸ��Ϣ
    $.ajax({
        url: '/api/v1.0/houses/'+houseId,
        type: 'get',
        dataType: 'json'
    }).done(function (resp) {
        if (resp.errno == '0'){
            var img_html = template('house-image-tmpl', {img_urls: resp.data.house.img_urls, price: resp.data.house.price});
            $('.swiper-wrapper').html(img_html);
            var html = template('house-detail-tmpl', {house: resp.data.house})
            $('.detail-con').html(html)

            // resp.data.user_idΪ����ҳ���û�,resp.data.house.user_idΪ����
            if (resp.data.user_id != resp.data.house.user_id){
                $('.book-house').prop('href', '')
                $('.book-house').show();
            }
            var mySwiper = new Swiper ('.swiper-container', {
                loop: true,
                autoplay: 2000,
                autoplayDisableOnInteraction: false,
                pagination: '.swiper-pagination',
                paginationType: 'fraction'
            })
        }
    })
});