$(function () {
  $(".js-upload-photos").click(function () {
    $("#fileupload").click();
    $('.spinner-border').show();
  });
  $("#fileupload").fileupload({
    dataType: 'json',
    add: function (e, data) {
      var fileSize = data.files[0].size;
      var maxSize = 5 * 1024 * 1024;
      if (fileSize > maxSize) {
        alert("File is too big! Maximum file size is 5MB.");
      } else {
        data.submit();
      }
    },
    done: function (e, data) {
      if (data.result.is_valid) {
        var tdId = $(this).closest("td").attr("id");
        cell_id = "#" + tdId
        $(cell_id).append(
          "<a href='" + data.result.url + "'>" + data.result.name + "</a>"
        )
        $(cell_id).append(
          "<input id=attached_file type=text name=attachment_id value=" +
          data.result.att_id + " hidden>"
        )
        $("#button-upload").hide()
        $('.spinner-border').hide();
      }
      else {
        alert(data.result.message);
      }
    }
  });
});